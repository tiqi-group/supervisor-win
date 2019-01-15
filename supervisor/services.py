# coding=utf-8
from __future__ import print_function

import argparse
import logging
import logging.handlers
import os
import re
import servicemanager
import socket
import sys
import traceback
import win32event
import win32service

import win32serviceutil

# supervisor{dir}/supervisor{package}
LOCAL_DIR = os.path.dirname(__file__)

# removes supervisor package directory from path
local_path_index = None
for index, path in enumerate(sys.path):
    if re.match(re.escape(path), LOCAL_DIR, re.U | re.I):
        local_path_index = index
        break
if local_path_index is not None:
    sys.path.pop(local_path_index)

try:
    import supervisor
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(LOCAL_DIR, '..')))


class SupervisorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "Supervisor"
    _svc_display_name_ = "Supervisor process monitor"
    _svc_description_ = "Supervisor: A Process Control System"
    _svc_deps_ = []

    _exe_name_ = sys.executable
    _exe_args_ = '"' + os.path.abspath(sys.argv[0]) + '"'

    # Additional settings passed to the supervisor config
    options = {
        # The supervisor is running in the background
        'daemonize': True
    }

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        #
        self.logger = logging.getLogger("supervisor.services")
        hdl = logging.handlers.RotatingFileHandler(os.path.join(os.getcwd(), "supervisor-service.log"),
                                                   maxBytes=1024 ** 2,
                                                   backupCount=3)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(hdl)

        self.stream_config = ''

    # noinspection PyBroadException
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # Supervisor process stop event
        try:
            self.logger.info("supervisorctl shutdown...")
            from supervisor import supervisorctl
            supervisorctl.main(("-c", self.stream_config, "shutdown"))
        except:
            self.logger.exception("shutdown execution failed")
        finally:
            win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main()

    # noinspection PyBroadException
    def main(self):
        """Starts running the supervisor"""
        try:
            from supervisor import supervisord
            self.logger.info("supervisor starting...")
            supervisord.main(("-c", self.stream_config))
        except:
            self.logger.exception("starting failed")


def parse_args_config(options, argv):
    args = []
    index = 0
    while True:
        try:
            item = argv[index]
        except IndexError:
            break
        for opts in options:
            if any(filter(item.startswith, opts['args'])):
                name = argv.pop(index)
                if name.find('=') > -1:
                    args.extend(item.split('='))
                    index -= 1
                    continue
                args.append(name)
                kwargs = opts.setdefault('kwargs', {})
                if kwargs.get('required', False):
                    try:
                        args.append(argv.pop(index))
                        index -= 1
                    except IndexError:
                        continue
                else:
                    index -= 1
        index += 1
    return args


def get_config_args(argv=None):
    argv = list(sys.argv) if argv is None else list(argv)
    options = [
        {'args': ('-h', '--help'),
         'kwargs': {'required': False,
                    'action': 'store_true'}},
        {'args': ('-c', '--config'),
         'kwargs': {'type': argparse.FileType('r'),
                    'help': 'full filepath to supervisor.conf',
                    'required': True}}
    ]
    args = parse_args_config(options, argv)
    return options, args, argv


def main():
    # starts in the main python directory.
    os.chdir(os.path.dirname(sys.executable))

    if len(sys.argv) == 1:
        # service must be starting...
        # for the sake of debugging etc, we use win32traceutil to see
        # any unhandled exceptions and print statements.
        print("supervisor service is starting...")
        print("(execute this script with '--help' if that isn't what you want)")
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(SupervisorService)
        # Now ask the service manager to fire things up for us...
        servicemanager.StartServiceCtrlDispatcher()
        print("supervisor service done!")
    else:
        # file configuration supervisord.conf
        options, args, srv_argv = get_config_args(sys.argv[1:])
        # print(args, srv_argv, sep='\n')
        parser = argparse.ArgumentParser(add_help=False)
        for opts in options:
            parser.add_argument(*opts['args'], **opts.get('kwargs', {}))
        options = parser.parse_args(args=args)
        try:
            options.config.close()
        except OSError:
            pass
        if options.help:
            parser.print_help(file=sys.stdout)
            print()
            srv_argv.append('-h')
        srv_argv.insert(0, sys.argv[0])
        win32serviceutil.HandleCommandLine(SupervisorService, argv=srv_argv)


if __name__ == '__main__':
    try:
        main()
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        print(" command execution failed ".center(35, '='))
        traceback.print_exc(limit=3)
