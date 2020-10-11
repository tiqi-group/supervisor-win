"""
Extension of existing classes by changing or adding behaviors.
"""
import ctypes
import errno
import msvcrt
import signal

import pywintypes
import random
import subprocess
import sys
import win32api
from win32file import ReadFile, WriteFile
from win32pipe import PeekNamedPipe

from supervisor.compat import as_string, as_bytes

__author__ = 'alex'


class DummyPopen(object):
    """Test process"""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.pid = random.randint(1, 500)
        self.returncode = 0


class Popen(subprocess.Popen):
    """
    Opens a new process (just as subprocess), but lets you know when the
    process was killed (using the kill attribute).
    """

    @property
    def message(self):
        if self.returncode is None:
            return 'still running'
        if self.returncode == 0:
            msg = "termination normal"
        elif self.returncode < 0:
            msg = "termination by signal"
        else:
            msg = "exit status %s" % (self.returncode,)
        return msg

    def send_os_signal(self, sig, proc_name):
        """Send signal by GenerateConsoleCtrlEvent"""
        status = ctypes.windll.kernel32.GenerateConsoleCtrlEvent(sig, self.pid)
        if status == 0:
            status = win32api.FormatMessage(win32api.GetLastError())
            status = as_string(status, errors='ignore')
            status = status.strip('\r\n')
        return "signal: %s (status %s)" % (proc_name, status)

    def kill2(self, sig, as_group=False, proc_name=None):
        if as_group:
            return self.taskkill()
        elif sig in [signal.CTRL_BREAK_EVENT, signal.CTRL_C_EVENT]:
            return self.send_os_signal(sig, proc_name)
        else:
            return self.send_signal(sig)

    def taskkill(self):
        """Kill process group"""
        output = subprocess.check_output(['taskkill',
                                          '/PID', str(self.pid),
                                          '/F', '/T'])
        return as_string(output, encoding=sys.getfilesystemencoding(), errors='ignore').strip()


class OutputStream(object):
    """
    Class of asynchronous reading of stdout, stderr data of a process
    """
    _os_file_handle = None
    bufsize = 1024 * 2  # 2Kb
    CR, LF = as_bytes("\r"), as_bytes("\n")
    CRLF = CR + LF

    def __init__(self, stream, text_mode=False):
        self.text_mode = text_mode
        self.stream = stream

    def __str__(self):
        return str(self.stream)

    @property
    def os_file_handle(self):
        if self._os_file_handle is None:
            self._os_file_handle = msvcrt.get_osfhandle(self.stream.fileno())
        return self._os_file_handle

    @classmethod
    def _translate_newlines(cls, data):
        return data.replace(cls.CRLF, cls.LF).replace(cls.CR, cls.LF)

    def read(self, bufsize=None):
        """Reads a data buffer the size of 'bufsize'"""
        if bufsize is None:
            bufsize = self.bufsize
        try:
            output, n_avail, n_message = PeekNamedPipe(self.os_file_handle, bufsize)
            if bufsize < n_avail:
                n_avail = bufsize
            if n_avail > 0:
                result, output = ReadFile(self.os_file_handle, n_avail, None)
        except (IOError, ValueError):
            return ''
        except pywintypes.error:
            why = sys.exc_info()[1]
            if why.winerror in (109, errno.ESHUTDOWN):
                return ''
            raise
        output = self._translate_newlines(output)
        return output or None


class InputStream(object):
    """Input stream nonblocking"""
    _os_file_handle = None

    def __init__(self, stream):
        self.stream = stream

    def __str__(self):
        return str(self.stream)

    @property
    def os_file_handle(self):
        if self._os_file_handle is None:
            self._os_file_handle = msvcrt.get_osfhandle(self.stream.fileno())
        return self._os_file_handle

    def close(self):
        try:
            self.stream.close()
        except(IOError, ValueError):
            pass
        return 0

    def write(self, input_buffer):
        """Write *data* to the subprocess's standard input."""
        if not self.stream:
            return None
        try:
            result, written = WriteFile(self.os_file_handle, bytearray(input_buffer))
        except (IOError, ValueError):
            return self.close()
        except pywintypes.error:
            why = sys.exc_info()[1]
            if why.winerror in (109, errno.ESHUTDOWN):
                return self.close()
            raise
        return written
