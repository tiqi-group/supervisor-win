"""
Extension of existing classes by changing or adding behaviors.
"""

import errno
import msvcrt

import pywintypes
import random
import subprocess
import sys
from win32file import ReadFile, WriteFile
from win32pipe import PeekNamedPipe

from supervisor.compat import as_string

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

    def kill2(self, sig, as_group=False):
        if as_group:
            return self.taskkill()
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
    read_bufsize = 1024 * 5  # 5Kb

    def __init__(self, stream, text_mode=False):
        self.text_mode = text_mode
        self.stream = stream

    def __str__(self):
        return str(self.stream)

    def read(self, bufsize=None):
        """Reads a data buffer the size of 'bufsize'"""
        if bufsize is None:
            bufsize = self.read_bufsize
        try:
            handle = msvcrt.get_osfhandle(self.stream.fileno())
            output, n_avail, n_message = PeekNamedPipe(handle, 0)
            if bufsize < n_avail:
                n_avail = bufsize
            if n_avail > 0:
                result, output = ReadFile(handle, n_avail, None)
        except (IOError, ValueError):
            return ''
        except pywintypes.error:
            why = sys.exc_info()[1]
            if why.winerror in (109, errno.ESHUTDOWN):
                return ''
            raise
        return output or None


class InputStream(object):
    """Input stream nonblocking"""
    encoding = sys.getfilesystemencoding()

    def __init__(self, stream):
        self.stream = stream

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
            handle = msvcrt.get_osfhandle(self.stream.fileno())
            result, written = WriteFile(handle, bytearray(input_buffer))
        except (IOError, ValueError):
            return self.close()
        except pywintypes.error:
            why = sys.exc_info()[1]
            if why.winerror in (109, errno.ESHUTDOWN):
                return self.close()
            raise
        return written
