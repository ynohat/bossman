Usage
=================

Bossman works on top of git working copies. Within a git working copy, Bossman will manage
resources using plugins according to a simple configuration file.

This page describes how to configure and operate bossman.

Configuration
________________________

Configuration tells bossman where resources are in the repository, and which
plugin to use to manage them.

It lives in a YAML file which is optional if the defaults are acceptable.

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

.. topic:: ``.gitignore``

  Bossman creates a ``.bossmancache`` file at the root of the repository containing cache entries to
  speed up specific lookups. This should be added to ``.gitignore``.

Targeting resources
__________________________________________________________

The ``glob`` argument is accepted by all bossman commands that interact with resources. It allows the
operator to restrict the command to a subset of resources. For example, to get the status of all dev resources:

.. code-block:: bash

  bossman status dev

It  can be provided multiple times, which will restrict operation to the subset of resources whose paths
match any of the patterns.

.. topic:: Partial vs. exact path matching

  By default, bossman performs partial matching, so the pattern need only match a part of the resource path.

  In some cases, typically when the name of a resource is the prefix of another resource, it is not possible
  to target only a specific resource with partial matching. For those cases, bossman supports an ``--exact-match``
  flag which requires the glob pattern to match the entire resource path.

.. topic:: Path matching syntax

  Bossman glob patterns use `Unix filename pattern matching <https://docs.python.org/3/library/fnmatch.html>`_.

  .. csv-table:: Pattern modifiers
    :header: "Pattern", "Meaning"

    ``*``, "Matches everything (including /)"
    ``?``, "Matches any single character (including /)"
    ``[seq]``, "Matches any character in _seq_"
    ``[!seq]``, "Matches any character _not_ in _seq_"

.. topic:: Examples

  Assuming you have the following resources in your repository:

  |  akamai/property/dev1
  |  akamai/requestcontrol/dev1
  |  akamai/property/dev2
  |  akamai/requestcontrol/dev2
  |  akamai/property/dev3
  |  akamai/requestcontrol/dev3
  |  akamai/property/integration
  |  akamai/property/prod
  |  akamai/property/prod-dark

  By default (without adding the ``--exact-match`` flag)

  * ``akamai``, ``akam`` or ``akamai/*``: will select all the resources
  * ``property`` or ``akamai/property``: will select all Akamai properties
  * ``dev[1-2]`` will select all Akamai resources (properties and requestcontrol) for dev1 and dev2
  * ``dev[!3]`` will select all Akamai resources (properties and requestcontrol) for dev1 and dev2

  Let's now imagine a case where an operation should be applied only to ``akamai/property/prod``.
  Because the default is to search, we cannot easily target it without also targeting prod-china,
  but we can use the ``--exact-match`` flag to clear the ambiguity. The following three examples
  would select only prod and not prod-cn:

  .. code-block:: bash

    bossman apply --exact-match */prod
    # -e is the short alias of --exact-match
    bossman apply -e */property/prod
    bossman apply -e akamai/property/prod

  To complete the illustration, the following examples use ``--exact-match`` to select both:

  .. code-block:: bash

    bossman apply -e */prod*
    bossman apply -e */property/prod*
    bossman apply -e akamai/property/prod*

.. topic:: Combining with shell expansion

  Some shells, such as ``bash`` and ``zsh`` also support expansion patterns that can complement bossman's
  pattern matching for very convenient operation. For example, to select all non-production resources with
  the set of resources above:

  .. code-block:: bash

    bossman status property/{dev\*,integration}
    # gets expanded to the following by the shell
    # bossman status property/dev* property/integration

``bossman version``
__________________________________________________________

This command outputs the version. It is the only command that can be run before ``bossman init``.

``bossman init``
__________________________________________________________

This command must be run before anything can be done by Bossman. It adjusts the ``.git/config``
file, adds a ``[bossman]`` section and extra refspecs to all remotess, to ensure
that git notes are properly pushed and pulled along with commits.

``bossman status [-e|--exact-match] [glob*]``
__________________________________________________________

Provides synthetic information about the state of resources managed by bossman.

``bossman apply [--force] [--dry-run] [--since=commit] [-e|--exact-match] [glob*]``
___________________________________________________________________________________________

Deploys all pending commits.

``--since`` limits deployment to commits after the given commit ref.

This should be avoided in general, since the default behavior is what one wants. It can be useful
in some cases to avoid extraneous deployments on e.g. long lived branches, which should never be
rebased.

Note that ``--since`` will deploy all commits *after* the given commit, non-inclusive.

For example:

Deploy the latest commit on the current branch::

  bossman apply --since HEAD^

Deploy all the commits after ``integration`` was merged to the current branch::

  bossman apply --since integration

``--dry-run`` simply evaluates which revisions would be deployed, without performing any action.

``--force`` indicates that the plugin should apply a change even if it might be unsafe. The implementation
and interpretation of "unsafe" is dependent on the plugin itself.

``bossman validate [-e|--exact-match] [glob*]``
__________________________________________________________

Validates the correctness of resources in the working copy.

This is the only command that does not operate on a commit.

``bossman (pre)prerelease [--rev HEAD] [-e|--exact-match] [-m|--message "MESSAGE"] [glob*]``
____________________________________________________________________

* ``prerelease``: makes a given revision available to an internal audience,
  typically for testing
* ``release``: makes a given revision available to the end users

``--rev`` can be any valid git commit reference, e.g.

* a commit hash (full or abbreviated)
* a tag name
* a branch name
* ``HEAD``
* a relative ref

``--message|-m`` will optionally annotate the release, when relevant


``bossman log [-e|--exact-match] [glob*]``
__________________________________________________________

Outputs the revision history of the selected resources.


Usage from CI
__________________________________________________________

It is possible to use ``bossman`` from automation, but the ``bossman (pre)release`` commands
require confirmation before they do anything, and expect to be run attended in a terminal, by default.

In automation, you will want to bypass confirmation, which can be done like this::

  bossman prerelease --yes
  bossman release --yes
