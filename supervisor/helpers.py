import Queue
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

    def kill(self):
        super(Popen, self).kill()
        self.killed = True


class StdQueue(Queue.Queue):
    """
    Together with a thread, ess class allows you to store data
    from the stream std [err, out]
    """
    def __init__(self, std, *args, **kwargs):
        Queue.Queue.__init__(self, *args, **kwargs)
        self.lock = threading.RLock()
        self.std = std

    def __getattr__(self, item):
        return getattr(self.std, item)

    def readline(self):
        if self.lock.acquire(False):
            try:
                self.put(self.std.readline())
            finally:
                self.lock.release()