# coding=utf-8
"""
Installation script for the supervisor as a service
To install the service on a terminal, as an administrator, run the command line:
python -m supervisor.services install -c "{path}\supervisord.conf"
"""
from __future__ import print_function

import argparse
import logging.handlers
import os
import re
import servicemanager
import socket
import sys
import traceback

import win32console
import win32event
import win32service

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
try:
    import _winreg as winreg
except ImportError:
    import winreg

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


class ConfigReg(object):
    """Saves the path to the supervisor.conf in the system registry"""
    service_name = "Supervisor Pyv{0.winver}".format(sys)

    def __init__(self, service_name=None):
        self.software_key = winreg.OpenKey(winreg.HKEY_CURRENT_CONFIG, "Software")
        if service_name is not None:
            self.service_name = service_name
        self.service_config_dir_key = self.service_name + " Service"
        self.service_name_key = "Name"
        self.config_name_key = "Config"

    def __getitem__(self, item):
        """Get value from registry"""
        with winreg.OpenKey(self.software_key, self.service_config_dir_key) as srv_key:
            value = winreg.QueryValue(srv_key, item)
        return value

    def __setitem__(self, key, value):
        """Set value to registry"""
        with winreg.CreateKey(self.software_key, self.service_config_dir_key) as srv_key:
            winreg.SetValue(srv_key, key, winreg.REG_SZ, value)

    def delete(self, key):
        with winreg.CreateKey(self.software_key, self.service_config_dir_key) as srv_key:
            try:
                winreg.DeleteKey(srv_key, key)
            except WindowsError:
                pass

    @property
    def filepath(self):
        """get supervisor config path"""
        return self[self.config_name_key]

    @filepath.setter
    def filepath(self, value):
        """set supervisor config path"""
        self[self.config_name_key] = value

    def get(self, name, *args):
        try:
            return self[name]
        except WindowsError:
            if args:
                return args[0]

    def close(self):
        """cleanup"""
        winreg.CloseKey(self.software_key)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()


config_reg = ConfigReg()


class StreamHandler(StringIO):
    """Limited io"""
    max_bytes = 1024 ** 2

    def __init__(self, writer):
        StringIO.__init__(self)
        self.writer = writer

    def write(self, s):
        s = s.rstrip('\n')
        if not s:
            return 0
        if self.tell() > self.max_bytes:
            self.truncate(0)
        self.writer(s)
        return StringIO.write(self, s)


class SupervisorService(win32serviceutil.ServiceFramework):
    _svc_name_ = config_reg.get(config_reg.service_name_key,
                                config_reg.service_name)
    _svc_display_name_ = _svc_name_ + " process monitor"
    _svc_description_ = "A process control system"
    _svc_deps_ = []

    _exe_name_ = config_reg.get("exe_name", sys.executable)
    _exe_args_ = config_reg.get("exe_args", '"' + os.path.abspath(sys.argv[0]) + '"')

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)

        # Gets the path of the registry configuration file
        try:
            config_reg_exc = None
            self.supervisor_conf = config_reg.filepath
        except WindowsError:
            config_reg_exc = traceback.format_exc()
            self.supervisor_conf = None

        # The log goes to the location of the configuration file
        if self.supervisor_conf is not None:
            config_dir = os.path.dirname(self.supervisor_conf)
        else:  # or to python home
            config_dir = os.getcwd()

        self.logger = logging.getLogger(__name__)
        log_path = os.path.join(config_dir, self._svc_name_.lower() + "-service.log")
        hdl = logging.handlers.RotatingFileHandler(log_path,
                                                   maxBytes=1024 ** 2,
                                                   backupCount=3)
        hdl.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(hdl)
        self.logger.info("supervisor config path: {0!s}".format(self.supervisor_conf))

        if config_reg_exc is not None:
            self.logger.error("* The service needs to be reinstalled")
            self.logger.error(config_reg_exc)
            logging.shutdown()
            exit(-1)

    @classmethod
    def set_service_name(cls, name):
        cls._svc_name_ = name

    @classmethod
    def set_service_display_name(cls, name):
        cls._svc_display_name_ = name

    @classmethod
    def set_config(cls, name, value):
        """Settings used by the service"""
        # temporary configuration that is used only during installation.
        setattr(cls, "_%s_" % name, value)
        # saves the new configuration to the system registry.
        config_reg[name] = value

    # noinspection PyBroadException
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # Supervisor process stop event
        stdout = StreamHandler(self.logger.info)
        stderr = StreamHandler(self.logger.error)
        try:
            self.logger.info("supervisorctl shutdown")
            from supervisor import supervisorctl
            supervisorctl.main(("-c", self.supervisor_conf, "shutdown"),
                               stdout=stdout, stderr=stderr)
        except SystemExit:
            pass  # normal exit
        except:
            self.logger.exception("supervisorctl shutdown execution failed")
        finally:
            logging.shutdown()
            stderr.close()
            stdout.close()
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
        stdout = StreamHandler(self.logger.info)
        stderr = StreamHandler(self.logger.error)
        try:
            from supervisor import supervisord
            self.logger.info("supervisor starting...")
            supervisord.main(("-c", self.supervisor_conf),
                             stdout=stdout, stderr=stderr)
            self.logger.info("supervisor shutdown")
        except:
            self.logger.exception("supervisor starting failed")
        finally:
            stdout.close()
            stderr.close()


def parse_args_config(options, argv):
    args = []
    index = 0
    while True:
        try:
            varg = argv[index]
            last_index = index
            index += 1
        except IndexError:
            break
        for opts in options:
            if any([varg == n for n in opts['args']]):
                index -= 1
                name = argv.pop(index)
                if name.find('=') > -1:
                    args.extend(varg.split('='))
                else:
                    args.append(name)
                    try:
                        args.append(argv.pop(index))
                    except IndexError:
                        break
                index = last_index
    return args


def check_existing_cmd(argv, *args):
    """Checks for cmd in argv"""
    for cmd in args:
        if cmd in argv:
            return True
    return False


def get_config_args(argv):
    argv = list(argv)
    options = [
        {'args': ('-h', '--help'),
         'kwargs': {'required': False, 'action': 'store_true'}},
        {'args': ('-c', '--config'),
         'kwargs': {'type': argparse.FileType('r'),
                    'help': 'full filepath to supervisor.conf',
                    'required': check_existing_cmd(argv, 'install', 'update')}},
        {'args': ('-sn', '--service-name'),
         'kwargs': {'required': False, 'type': str}},
        {'args': ('-sdn', '--service-display-name'),
         'kwargs': {'required': False, 'type': str}},
    ]
    args = parse_args_config(options, argv)
    return options, args, argv


def runner(argv):
    if len(argv) == 1:
        # service must be starting...
        # for the sake of debugging etc, we use win32traceutil to see
        # any unhandled exceptions and print statements.
        print("supervisor service is starting...")
        print("(execute this script with '-h' or '--help' if that isn't what you want)")
        win32console.AllocConsole()
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(SupervisorService)
        # Now ask the service manager to fire things up for us...
        servicemanager.StartServiceCtrlDispatcher()
        print("supervisor service done!")
    else:
        # file configuration supervisord.conf
        options, args, srv_argv = get_config_args(argv[1:])
        # print(args, srv_argv, sep='\n')
        parser = argparse.ArgumentParser(add_help=False)
        for opts in options:
            parser.add_argument(*opts['args'], **opts.get('kwargs', {}))
        options = parser.parse_args(args=args)
        if options.config:
            try:
                options.config.close()
            except OSError:
                pass
        if options.help:
            parser.print_help(file=sys.stdout)
            print()
        # supervisor conf
        elif options.config:
            config_reg.filepath = options.config.name
        # custom service name
        if options.service_name:
            config_reg[config_reg.service_name_key] = options.service_name
            SupervisorService.set_service_name(options.service_name)  # runtime only
            SupervisorService.set_service_display_name(options.service_name + " process monitor")
        # custom service display name
        if options.service_display_name:
            SupervisorService.set_service_display_name(options.service_display_name)
        srv_argv.insert(0, argv[0])
        # self executable (Scripts)
        filepath = os.path.dirname(argv[0])
        filename = os.path.basename(argv[0])
        name, extension = os.path.splitext(filename)
        if not re.match(r"\.py[cod]*$", extension, re.I) and \
                check_existing_cmd(srv_argv, 'install', 'update'):
            executable = os.path.join(filepath, name + '.exe')
            SupervisorService.set_config("exe_name", executable)
            SupervisorService.set_config("exe_args", '')
        elif check_existing_cmd(srv_argv, 'remove'):
            config_reg.delete('exe_name')
            config_reg.delete('exe_args')
        win32serviceutil.HandleCommandLine(SupervisorService, argv=srv_argv)


def main(argv=None):
    if argv is None:
        argv = sys.argv
    # starts in the main python directory.
    os.chdir(os.path.dirname(sys.executable))
    try:
        runner(argv)
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as exc:
        print(" command execution failed ".center(35, '='))
        if isinstance(exc, WindowsError):
            print("Administrator permission required!",
                  file=sys.stderr)
        traceback.print_exc(limit=3)


if __name__ == '__main__':
    main(sys.argv)
