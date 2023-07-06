# coding=utf-8
import errno
import msvcrt
import random
import sys

import pywintypes
from win32file import ReadFile, WriteFile
from win32pipe import PeekNamedPipe

from supervisor.compat import as_bytes

__author__ = "alex"


class DummyPopen(object):
    """Test process"""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.pid = random.randint(1, 500)
        self.returncode = 0


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
            return ""
        except pywintypes.error:
            why = sys.exc_info()[1]
            if why.winerror in (109, errno.ESHUTDOWN):
                return ""
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
        except (IOError, ValueError):
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
