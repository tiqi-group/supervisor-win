Windows idiosyncrasies
======================

Stop signals
------------
Supervisor for windows supports the following values for `stopsignal`:

* SIGTERM
* CTRL_C_EVENT
* CTRL_BREAK_EVENT

These correspond to ``SIGTERM``, ``SIGINT`` and ``SIGBREAK`` being raised respectively.

Note that when run as a Windows service, supervisor is not guaranteed to be able to raise ``SIGINT`` in a child process.
The child process must call ``SetConsoleCtrlHandler(NULL, false)`` (see the `Windows API documentation <https://docs.microsoft.com/en-us/windows/console/setconsolectrlhandler>`_)  in order to be able to accept the interrupt. 
If your child process is running a Python script, this can be achieved be calling:

.. code-block:: python
    
    import win32api
    win32api.SetConsoleCtrlHandler(None, False)
    
from within your code.

This requirement is due to the way supervisor launches subprocesses (with the ``CREATE_NEW_PROCESS_GROUP`` creation flag).
A thorough discussion of this limitation can be found on `Stack Overflow <https://stackoverflow.com/a/35792192>`_.
