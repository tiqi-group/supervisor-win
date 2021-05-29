Supervisor for Windows
=========================

.. image:: https://travis-ci.org/alexsilva/supervisor.svg?branch=windows
    :target: https://travis-ci.org/alexsilva/supervisor

Supervisor is a client/server system that allows its users to
control a number of processes on Windows operating system.

Supported Platforms
-------------------

Supervisor has been tested (Python 2.7/3.7 [32/64 bit]) and is known to run on Windows `10` / `Server 2012`.

* New processes are created by the subprocess standard lib.
* Some specific features of OS Linux have been disabled and others were adapted to the Windows OS.
* The process control (supervisorctl) works and management processes correctly, as well as control via web!

How to install ?
----------------
Installation can be done via pip

``python -m pip install supervisor-win``

* Note that the package name is different from the unix version.
 
It is also possible to install the development version
``python -m pip install git+https://github.com/alexsilva/supervisor@windows``

Install as Windows service
--------------------------
To install supervisor as a windows service run the command

``python -m supervisor.services install -c {system-path}\\supervisord.conf``

Or install from the utility script (``{PythonHome}\\Scripts`` directory must be in the system path)

``supervisor_service.exe install -c {system-path}\\supervisord.conf``

Supervisor for Unix-Like System
-------------------------------
`Original project for unix-like system <https://github.com/Supervisor/supervisor>`_

Documentation
-------------

You can view the current Supervisor documentation online `in HTML format
<http://supervisord.org/>`_ .  This is where you should go for detailed
installation and configuration documentation.

Windows specific documentation can be found `here <https://github.com/alexsilva/supervisor/blob/windows/docs/windows.rst>`_.

Mailing list, Reporting Bugs, and Viewing the Source Repository
---------------------------------------------------------------

You may subscribe to the `Supervisor-users mailing list
<http://lists.supervisord.org/mailman/listinfo/supervisor-users>`_.

Please report bugs in the `Github issue tracker
<https://github.com/alexsilva/supervisor/issues>`_.

You can view the source repository for supervisor via
`https://github.com/alexsilva/supervisor
<https://github.com/alexsilva/supervisor>`_

Contributing
------------
If you want to help with the development send a  `Pull Requests
<https://github.com/alexsilva/supervisor/pulls>`_


