Resources and Development
=========================

Bug Tracker
-----------

Supervisor has a bugtracker where you may report any bugs or other
errors you find.  Please report bugs to the `GitHub issues page
<https://github.com/supervisor/supervisor/issues>`_.

Version Control Repository
--------------------------

You can also view the `Supervisor version control repository
<https://github.com/Supervisor/supervisor>`_.

Contributing
------------

We'll review contributions from the community in
`pull requests <https://help.github.com/articles/using-pull-requests>`_
on GitHub.

Sponsoring
----------

If you'd like to sponsor further Supervisor development (for custom
projects), please let one of the authors know.

Author Information
------------------

The following people are responsible for creating Supervisor.

Primary Authors and Maintainers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- `Chris McDonough <http://plope.com>`_ is the original author of Supervisor
  and the primary maintainer.

Contributors
~~~~~~~~~~~~

- Anders Quist: Anders contributed the patch that was the basis for
  Supervisor’s ability to reload parts of its configuration without
  restarting.

- Derek DeVries: Derek did the web design of Supervisor’s internal web
  interface and website logos.

- Guido van Rossum: Guido authored ``zdrun`` and ``zdctl``, the
  programs from Zope that were the original basis for Supervisor.  He
  also created Python, the programming language that Supervisor is
  written in.

- Jason Kirtland: Jason fixed Supervisor to run on Python 2.6 by
  contributing a patched version of Medusa (a Supervisor dependency)
  that we now bundle.

- Roger Hoover: Roger added support for spawning FastCGI programs. He
  has also been one of the most active mailing list users, providing
  his testing and feedback.

- Siddhant Goel: Siddhant worked on :program:`supervisorctl` as our
  Google Summer of Code student for 2008. He implemented the ``fg``
  command and also added tab completion.
