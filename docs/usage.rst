Usage
=================

Bossman works on top of git working copies. Within a git working copy,
Bossman will manage resources using plugins according to a simple configuration file.

Configuration
________________________

Configuration is a YAML file which is optional if the defaults are acceptable.

It should be called ``.bossman`` and reside at the root of the repository. It should
be added to source control.

It should have a single ``resources`` field defining associations between file match
patterns and resource plugins:

.. code-block:: yaml

    resources:
    - module: bossman.plugins.akamai.property
      pattern: akamai/property/{name}

The ``module`` field must be an importable module on the python path. Multiple resources
may reference the same module.

The ``pattern`` field is a path, relative to the root of the repository. ``{placeholders}``
like ``{name}`` in the example above will always match a single path component (no slashes).
The supported placeholders are specific to each plugin.

In addition to the ``module`` and ``pattern`` fields, each resouce group can define
additional plugin-specific parameters in an ``options`` field.

See the :ref:`plugins` documentation pages for details.

``.gitignore``
_________________________________________________________

Bossman creates a ``.bossmancache`` file at the root of the repository containing cache entries to
speed up specific lookups. This should be added to ``.gitignore``.

``bossman version``
__________________________________________________________

This command outputs the version. It is the only command that can be run before ``bossman init``.

``bossman init``
__________________________________________________________

This command must be run before anything can be done by Bossman. It adjusts the ``.git/config``
file, adding a ``[bossman`` section, and adds extra refspecs to all remotess, to ensure
that git notes are properly pushed and pulled along with commits.

``bossman status [glob]``
__________________________________________________________

todo

``bossman apply [--rev HEAD] [glob]``
__________________________________________________________

todo

``bossman validate [glob]``
__________________________________________________________

todo

``bossman prerelease|release [--rev HEAD] [glob]``
__________________________________________________________

``--rev`` can be any valid git commit reference, e.g.

* a commit hash (full or abbreviated)
* a tag name
* a branch name
* ``HEAD``
* a relative ref

``bossman log [glob]``
__________________________________________________________

todo

