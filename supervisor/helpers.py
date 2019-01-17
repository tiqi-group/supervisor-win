import subprocess
import threading

__author__ = 'alex'

"""
Extension of existing classes by changing or adding behaviors.
"""


class Popen(subprocess.Popen):
    """
    Opens a new process (just as subprocess), but lets you know when the
    process was killed (using the kill attribute).
    """

    def __init__(self, *args, **kwargs):
        super(Popen, self).__init__(*args, **kwargs)
        self.killed = False

    def send_signal(self, sig):
        super(Popen, self).send_signal(sig)
        self.killed = True


class StreamAsync(threading.Thread):
    """
    Class of asynchronous reading of stdout data, stderr of a process
    """

    def __init__(self, stream, *args, **kwargs):
        threading.Thread.__init__(self, *args, **kwargs)
        self.setDaemon(True)
        self.stream = stream
        self.queue = set()
        self._event = threading.Event()
        self.mutex = threading.Lock()
        self.res_put = threading.Condition(self.mutex)
        self.res_get = threading.Condition(self.mutex)

    def __getattr__(self, item):
        return getattr(self.stream, item)

    def run(self):
        while not self._event.is_set():
            try:
                data = self.stream.readline()
            except IOError:
                # occurs when the supervisor is
                # restarted with the reload command
                break
            if not data:
                break
            self.res_put.acquire()
            try:
                self.queue.add(data)
                self.res_put.wait()
            finally:
                self.res_put.release()

    def stop(self):
        """Stops thread execution"""
        self._event.set()
        self.readline()

    def readline(self):
        """read one line from queue"""
        self.res_get.acquire()
        try:
            return self.queue.pop()
        except KeyError:
            return None
        finally:
            self.res_put.notify()
            self.res_get.release()
