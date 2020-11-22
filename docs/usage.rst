Usage
=================

Bossman works on top of git working copies. Within a git working copy, Bossman will manage
resources using plugins according to a simple configuration file.

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
file, adds a ``[bossman]`` section and extra refspecs to all remotess, to ensure
that git notes are properly pushed and pulled along with commits.

The ``glob`` argument
__________________________________________________________

The ``glob`` argument is accepted by all bossman commands that interact with resources. It allows the
operator to restrict the command to a subset of resources.

It  can be provided multiple times, which will restrict operation to the subset of resources whose paths
match any of the patterns.

.. topic:: Path matching details

  It performs partial matching on resource paths using `Unix filename pattern matching <https://docs.python.org/3/library/fnmatch.html>`_.

  .. csv-table:: Pattern modifiers
    :header: "Pattern", "Meaning"

    ``*``, "Matches everything (including /)"
    ``?``, "Matches any single character (including /)"
    ``[seq]``, "Matches any character in _seq_"
    ``[!seq]``, "Matches any character _not_ in _seq_"

  Assuming you have the following resources in your repository:

  |  akamai/property/dev1
  |  akamai/requestcontrol/dev1
  |  akamai/property/dev2
  |  akamai/requestcontrol/dev2
  |  akamai/property/dev3
  |  akamai/requestcontrol/dev3
  |  akamai/property/integration
  |  akamai/property/prod

  * ``akamai``, ``akam`` or ``akamai/*``: will select all the resources
  * ``property`` or ``akamai/property``: will select all Akamai properties
  * ``dev[1-2]`` will select all Akamai resources (properties and requestcontrol) for dev1 and dev2
  * ``dev[!3]`` will select all Akamai resources (properties and requestcontrol) for dev1 and dev2

.. topic:: Combining with shell expansion

  Some shells, such as ``bash`` and ``zsh`` also support expansion patterns that can complement bossman's
  pattern matching for very convenient operation. For example, to select all non-production resources with
  the set of resources above:

  .. code-block:: bash

    bossman status property/{dev\*,integration}
    # gets expanded to the following by the shell
    # bossman status property/dev* property/integration


``bossman status [glob*]``
__________________________________________________________

Provides synthetic information about the state of resources managed by bossman.

``bossman apply [glob*]``
__________________________________________________________

Deploys all pending commits.

``bossman validate [glob*]``
__________________________________________________________

Validates the correctness of resources in the working copy.

This is the only command that does not operate on a commit.

``bossman prerelease|release [--rev HEAD] [glob*]``
__________________________________________________________

* ``prerelease``: makes a given revision available to an internal audience,
  typically for testing
* ``release``: makes a given revision available to the end users

``--rev`` can be any valid git commit reference, e.g.

* a commit hash (full or abbreviated)
* a tag name
* a branch name
* ``HEAD``
* a relative ref

``bossman log [glob*]``
__________________________________________________________

Outputs the revision history of the selected resources.
