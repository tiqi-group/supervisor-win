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

    def send_signal(self, sig):
        super(Popen, self).send_signal(sig)
        self.killed = True


class StreamAsync(Queue.Queue, threading.Thread):
    """
    Class of asynchronous reading of stdout data, stderr of a process
    """

    def __init__(self, stream, auto_start=True, *args, **kwargs):
        Queue.Queue.__init__(self, *args, **kwargs)
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.stream = stream
        if auto_start:
            self.start()

    def __getattr__(self, item):
        return getattr(self.stream, item)

    def run(self):
        for line in iter(self.stream.readline, ''):
            self.put(line)
