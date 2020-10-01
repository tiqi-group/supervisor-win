"""
Extension of existing classes by changing or adding behaviors.
"""

import errno
import msvcrt

import pywintypes
import random
import subprocess
import sys
import threading
from win32file import ReadFile
from win32pipe import PeekNamedPipe

from supervisor.compat import StringIO
from supervisor.compat import as_string
from supervisor.compat import queue

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

    @staticmethod
    def _translate_newlines(data):
        return data.replace("\r\n", "\n").replace("\r", "\n")

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

        if self.text_mode:
            # Conversion of the line and decoding to unicode.
            output = self._translate_newlines(output)
            # it can sometimes be empty but does not mean that the channel has been closed.
            output = output or None
        return output


class StreamAsync(threading.Thread):
    """
    Class of asynchronous reading of stdout data, stderr of a process
    """

    read_bufsize = 1024 * 5  # 5Kb
    fifo_size = 100

    def __init__(self, stream, *args, **kwargs):
        threading.Thread.__init__(self, *args, **kwargs)
        self.setDaemon(True)
        self.stream = stream
        self.queue = queue.Queue(self.fifo_size)
        self._event = threading.Event()

    def __getattr__(self, item):
        return getattr(self.stream, item)

    def run(self):
        while not self._event.is_set():
            try:
                output = self.stream.readline()
                if not output:
                    break
            except (IOError, ValueError):
                # occurs when the supervisor is
                # restarted with the reload command
                break
            else:
                self.queue.put(output, block=not self._event.is_set())

    def close(self):
        """Stops thread execution"""
        self._event.set()

    def read(self, bufsize=None):
        """Reads a data buffer"""
        buffer = StringIO()
        bufsize = bufsize or self.read_bufsize
        try:
            while True:
                # read until empty
                buffer.write(self.queue.get_nowait())
                if buffer.tell() > bufsize:
                    break
        except queue.Empty:
            pass
        if buffer.tell() > 0:
            value = buffer.getvalue()
            del buffer
        else:
            value = None
        return value
