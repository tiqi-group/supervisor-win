Windows idiosyncrasies
======================

Standard stop signals
------------
Supervisor for windows supports the following values for ``stopsignal``:

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


Window events
-------------
Supervisor for windows also supports sending Window events to graphical applications.
These include events such as ``WM_CLOSE``.

The ``stopsignal`` configuration option thus supports strings such as ``WM_CLOSE`` or negative integers that correspond to the negative of the window event.
For example, ``WM_CLOSE`` event is documented as ``16`` (see `here <https://docs.microsoft.com/en-us/windows/win32/winmsg/wm-close>`_), so ``stopsignal=-16`` is equivalent to ``stopsignal=WM_CLOSE. 
This allows private window events (with values in the range documented `here <https://docs.microsoft.com/en-us/windows/win32/winmsg/wm-user>`_) to also be sent should your application support them.
Remember, ``stopsignal`` must be specified as the negative of the event id.

Note: The use of the negative id number is so that supervisor can distinguish them from the standard signals documented above. The Windows event id number is converted to a positive integer just prior to sending it to your application.