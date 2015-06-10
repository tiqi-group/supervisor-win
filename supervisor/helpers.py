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


class StdQueueAsync(Queue.Queue, threading.Thread):
    """
    Together with a thread, ess class allows you to store data
    from the stream std [err, out]
    """

    def __init__(self, std, nline=5, start=True, *args, **kwargs):
        Queue.Queue.__init__(self, *args, **kwargs)
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.std = std
        self.nline = nline
        if start:
            self.start()

    def __getattr__(self, item):
        return getattr(self.std, item)

    def run(self):
        for line in iter(self.std.readline, ''):
            self.put(line)
