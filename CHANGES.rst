4.4.0
-----------------------------
- Merge supervisor unix changes from 4.2.0.dev0 (master)
- Support for web servers that supports shared socket (fastcgi).
- Support for sending Windows signals. (signal CTRL_C_EVENT|CTRL_BREAK_EVENT)
- Possibility to configure a custom service name (options: '--service-name' or '--service-display-name').

4.3.0
-----------------------------
- Merge supervisor unix changes from 4.2.0.dev0 (master)
- Stop process group with task taskkill
- Fixing service data output issues

4.2.0
-----------------------------
- Merge supervisor unix changes from 4.2.0.dev0 (master)
- Fixed data output via eventlisterner

4.1.0
-----------------------------
- Merge supervisor unix changes from v4.1.0.dev0 (master)

4.0.3
-----------------------------
- Merge supervisor unix changes until
- https://github.com/Supervisor/supervisor/commit/3a956ce4913e25c18760f4430220b6d5df866c7f).
- Fixed process exit detection.

4.0.2
-----------------------------
- Process restart correction
- Fixed ``DeprecationWarning: Parameters to load are deprecated. Call
  .resolve and .require separately.`` on setuptools >= 11.3.


4.0.1
-----------------------------
- Bug fixes (covered by unit tests).
- Supervisor installation script as a service.
- python -m supervisor.services install -c "{path}\supervisord.conf"
