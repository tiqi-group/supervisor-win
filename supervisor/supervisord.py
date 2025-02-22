#!/usr/bin/env python

"""supervisord -- run a set of applications as daemons.

Usage: %s [options]

Options:
-c/--configuration FILENAME -- configuration file path (searches if not given)
-n/--nodaemon -- run in the foreground (same as 'nodaemon=true' in config file)
-s/--silent -- no logs to stdout (maps to 'silent=true' in config file)
-h/--help -- print this usage message and exit
-v/--version -- print supervisord version number and exit
-u/--user USER -- run supervisord as this user (or numeric uid)
-m/--umask UMASK -- use this umask for daemon subprocess (default is 022)
-d/--directory DIRECTORY -- directory to chdir to when daemonized
-l/--logfile FILENAME -- use FILENAME as logfile path
-y/--logfile_maxbytes BYTES -- use BYTES to limit the max size of logfile
-z/--logfile_backups NUM -- number of backups to keep when max bytes reached
-e/--loglevel LEVEL -- use LEVEL as log level (debug,info,warn,error,critical)
-j/--pidfile FILENAME -- write a pid file for the daemon process to FILENAME
-i/--identifier STR -- identifier used for this instance of supervisord
-q/--childlogdir DIRECTORY -- the log directory for child process logs
-k/--nocleanup --  prevent the process from performing cleanup (removal of
                   old automatic child log files) at startup.
-a/--minfds NUM -- the minimum number of file descriptors for start success
-t/--strip_ansi -- strip ansi escape codes from process output
--minprocs NUM  -- the minimum number of processes available for start success
--profile_options OPTIONS -- run supervisord under profiler and output
                             results based on OPTIONS, which  is a comma-sep'd
                             list of 'cumulative', 'calls', and/or 'callers',
                             e.g. 'cumulative,callers')
"""

import os
import signal
import time

from supervisor.compat import as_string
from supervisor.medusa import asyncore_25 as asyncore
from supervisor.options import ServerOptions
from supervisor.options import decode_wait_status
from supervisor.options import signame
from supervisor import events
from supervisor.states import SupervisorStates
from supervisor.states import getProcessStateDescription


class Supervisor(object):
    stopping = False  # set after we detect that we are handling a stop request
    lastshutdownreport = 0  # throttle for delayed process error reports at stop
    process_groups = None  # map of process group name to process group object
    stop_groups = None  # list used for priority ordered shutdown

    def __init__(self, options):
        self.options = options
        self.process_groups = {}
        self.ticks = {}

    def main(self):
        if not self.options.first:
            # prevent crash on libdispatch-based systems, at least for the
            # first request
            try:
                self.options.cleanup_fds()
            except NotImplementedError:
                pass

        self.options.set_uid_or_exit()

        if self.options.first:
            try:
                self.options.set_rlimits_or_exit()
            except NotImplementedError:
                pass
        # this sets the options.logger object
        # delay logger instantiation until after setuid
        self.options.make_logger()

        if not self.options.nocleanup:
            # clean up old automatic logs
            self.options.clear_autochildlogdir()

        self.run()

    def run(self):
        self.process_groups = {}  # clear
        self.stop_groups = None  # clear
        events.clear()
        self.make_job_handler()  # container
        try:
            for config in self.options.process_group_configs:
                self.add_process_group(config)
            self.options.openhttpservers(self)
            self.options.setsignals()
            if not self.options.nodaemon and self.options.first:
                try:
                    self.options.daemonize()
                except NotImplementedError:
                    pass
            # writing pid file needs to come *after* daemonizing or pid
            # will be wrong
            self.options.write_pidfile()
            self.runforever()
        except:
            raise
        finally:
            self.options.cleanup()
            if self.options.job_handler:
                self.options.job_handler.terminate()

    def make_job_handler(self):
        """Object that manages subprocesses (simulates a process tree, causing the subprocess
        to be closed if the supervisor stops working unexpectedly)
        """
        try:
            from supervisor.process import ProcessJobHandler

            self.options.job_handler = ProcessJobHandler(os.getpid())
        except (
            ImportError,
            Exception,
        ):  # Supervisor can not stop due to execution failure
            self.options.job_handler = None
        return self.options.job_handler

    def diff_to_active(self):
        new = self.options.process_group_configs
        cur = [group.config for group in self.process_groups.values()]

        curdict = dict(zip([cfg.name for cfg in cur], cur))
        newdict = dict(zip([cfg.name for cfg in new], new))

        added = [cand for cand in new if cand.name not in curdict]
        removed = [cand for cand in cur if cand.name not in newdict]

        changed = [cand for cand in new if cand != curdict.get(cand.name, cand)]

        return added, changed, removed

    def add_process_group(self, config):
        name = config.name
        if name not in self.process_groups:
            config.after_setuid()
            self.process_groups[name] = config.make_group()
            events.notify(events.ProcessGroupAddedEvent(name))
            self.options.logger.info("process group added: '%s'" % name)
            return True
        return False

    def remove_process_group(self, name):
        if self.process_groups[name].get_unstopped_processes():
            return False
        self.process_groups[name].before_remove()
        del self.process_groups[name]
        events.notify(events.ProcessGroupRemovedEvent(name))
        self.options.logger.info("process group removed: '%s'" % name)
        return True

    def get_process_map(self):
        process_map = {}
        for group in self.process_groups.values():
            process_map.update(group.get_dispatchers())
        return process_map

    def shutdown_report(self):
        unstopped = []

        for group in self.process_groups.values():
            unstopped.extend(group.get_unstopped_processes())

        if unstopped:
            # throttle 'waiting for x to die' reports
            now = time.time()
            if now > (self.lastshutdownreport + 3):  # every 3 secs
                names = [as_string(p.config.name) for p in unstopped]
                namestr = ", ".join(names)
                self.options.logger.info("waiting for %s to die" % namestr)
                self.lastshutdownreport = now
                for proc in unstopped:
                    state = getProcessStateDescription(proc.get_state())
                    self.options.logger.blather(
                        "%s state: %s" % (proc.config.name, state)
                    )
        return unstopped

    def ordered_stop_groups_phase_1(self):
        if self.stop_groups:
            # stop the last group (the one with the "highest" priority)
            self.stop_groups[-1].stop_all()

    def ordered_stop_groups_phase_2(self):
        # after phase 1 we've transitioned and reaped, let's see if we
        # can remove the group we stopped from the stop_groups queue.
        if self.stop_groups:
            # pop the last group (the one with the "highest" priority)
            group = self.stop_groups.pop()
            if group.get_unstopped_processes():
                # if any processes in the group aren't yet in a
                # stopped state, we're not yet done shutting this
                # group down, so push it back on to the end of the
                # stop group queue
                self.stop_groups.append(group)

    @staticmethod
    def dispatcher_handle_event(dispatcher, handle_event):
        """Calls the dispatcher event and handles errors"""
        try:
            return getattr(dispatcher, handle_event)()
        except asyncore.ExitNow:
            raise
        except:
            return dispatcher.handle_error()

    def runforever(self):
        events.notify(events.SupervisorRunningEvent())
        socket_map = self.options.get_socket_map()

        while True:
            combined_map = {}
            combined_map.update(socket_map)
            combined_map.update(self.get_process_map())
            pgroups = list(self.process_groups.values())
            pgroups.sort()

            if self.options.mood < SupervisorStates.RUNNING:
                if not self.stopping:
                    # first time, set the stopping flag, do a
                    # notification and set stop_groups
                    self.stopping = True
                    self.stop_groups = pgroups[:]
                    events.notify(events.SupervisorStoppingEvent())

                self.ordered_stop_groups_phase_1()

                if not self.shutdown_report():
                    # if there are no unstopped processes (we're done
                    # killing everything), it's OK to shutdown or reload
                    raise asyncore.ExitNow

            for fd, dispatcher in combined_map.items():
                if dispatcher.readable():
                    if hasattr(dispatcher, "socket"):
                        self.options.poller.register_readable(dispatcher.socket)
                    else:
                        self.dispatcher_handle_event(dispatcher, "handle_read_event")
                if dispatcher.writable():
                    if hasattr(dispatcher, "socket"):
                        self.options.poller.register_writable(dispatcher.socket)
                    else:
                        self.dispatcher_handle_event(dispatcher, "handle_write_event")

            readables, writables = self.options.poller.poll(self.options.delaysecs)

            for fd in readables:
                if fd in combined_map:
                    try:
                        dispatcher = combined_map[fd]
                        self.options.logger.blather(
                            "read event caused by %(dispatcher)s", dispatcher=dispatcher
                        )
                        dispatcher.handle_read_event()
                    except asyncore.ExitNow:
                        raise
                    except:
                        combined_map[fd].handle_error()

            for fd in writables:
                if fd in combined_map:
                    try:
                        dispatcher = combined_map[fd]
                        self.options.logger.blather(
                            "write event caused by %(dispatcher)s",
                            dispatcher=dispatcher,
                        )
                        dispatcher.handle_write_event()
                    except asyncore.ExitNow:
                        raise
                    except:
                        combined_map[fd].handle_error()

            for group in pgroups:
                group.transition()

            self.reap()
            self.handle_signal()
            self.tick()

            if self.options.mood < SupervisorStates.RUNNING:
                self.ordered_stop_groups_phase_2()

            if self.options.test:
                break

            try:
                # Avoid overloading the processor
                time.sleep(self.options.delaysecs)
            except IOError:
                continue

    def tick(self, now=None):
        """Send one or more 'tick' events when the timeslice related to
        the period for the event type rolls over"""
        if now is None:
            # now won't be None in unit tests
            now = time.time()
        for event in events.TICK_EVENTS:
            period = event.period
            last_tick = self.ticks.get(period)
            if last_tick is None:
                # we just started up
                last_tick = self.ticks[period] = timeslice(period, now)
            this_tick = timeslice(period, now)
            if this_tick != last_tick:
                self.ticks[period] = this_tick
                events.notify(event(this_tick, self))

    def reap(self, once=False, recursionguard=0):
        pid, sts = self.options.waitpid()
        if pid is None or recursionguard == 100:
            return
        try:
            subprocess = self.options.get_pid_history(pid)
        except KeyError:
            _, msg = decode_wait_status(sts)
            self.options.logger.info("reaped unknown pid %s (%s)" % (pid, msg))
        else:
            subprocess.finish(pid, sts)
            self.options.remove_pid_history(pid)
        if not once:
            # keep reaping until no more kids to reap, but don't recurse
            # infintely
            self.reap(once=False, recursionguard=recursionguard + 1)

    def handle_signal(self):
        sig = self.options.get_signal()
        if sig:
            if sig in (signal.SIGTERM, signal.SIGINT):
                self.options.logger.warn(
                    "received %s indicating exit request" % signame(sig)
                )
                self.options.mood = SupervisorStates.SHUTDOWN
            elif sig == signal.SIGABRT:
                if self.options.mood == SupervisorStates.SHUTDOWN:
                    self.options.logger.warn(
                        "ignored %s indicating restart request (shutdown in progress)"
                        % signame(sig)
                    )
                else:
                    self.options.logger.warn(
                        "received %s indicating restart request" % signame(sig)
                    )
                    self.options.mood = SupervisorStates.RESTARTING
            # elif sig == signal.SIGCHLD:
            #     self.options.logger.debug('received %s indicating a child quit' % signame(sig))
            # elif sig == signal.SIGUSR2:
            #     self.options.logger.info('received %s indicating log reopen request' % signame(sig))
            #     self.options.reopenlogs()
            #     for group in self.process_groups.values():
            #         group.reopenlogs()
            else:
                self.options.logger.blather(
                    "received %s indicating nothing" % signame(sig)
                )

    def get_state(self):
        return self.options.mood


def timeslice(period, when):
    return int(when - (when % period))


# profile entry point
def profile(cmd, globals, locals, sort_order, callers):  # pragma: no cover
    try:
        import cProfile as profile
    except ImportError:
        import profile
    import pstats
    import tempfile

    fd, fn = tempfile.mkstemp()
    try:
        profile.runctx(cmd, globals, locals, fn)
        stats = pstats.Stats(fn)
        stats.strip_dirs()
        # calls,time,cumulative and cumulative,calls,time are useful
        stats.sort_stats(*sort_order or ("cumulative", "calls", "time"))
        if callers:
            stats.print_callers(0.3)
        else:
            stats.print_stats(0.3)
    finally:
        os.close(fd)
        os.remove(fn)


# Main program
def main(args=None, test=False, stdout=None, stderr=None):
    # assert os.name == "posix", "This code makes Unix-specific assumptions"
    # if we hup, restart by making a new Supervisor()
    first = True
    while 1:
        options = ServerOptions()
        # output config
        if stdout is not None:
            options.stdout = stdout
        if stderr is not None:
            options.stderr = stderr
        options.realize(args, doc=__doc__)
        options.first = first
        options.test = test
        try:
            if options.profile_options:
                sort_order, callers = options.profile_options
                profile("go(options)", globals(), locals(), sort_order, callers)
            else:
                go(options)
        finally:
            options.close_httpservers()
            options.close_logger()
        first = False
        if test or (options.mood < SupervisorStates.RESTARTING):
            break


def go(options):  # pragma: no cover
    d = Supervisor(options)
    try:
        d.main()
    except asyncore.ExitNow:
        d.options.logger.info("exit now...")


if __name__ == "__main__":  # pragma: no cover
    main()
