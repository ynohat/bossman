
Akamai Property
================================

This page provides reference information about how bossman commands relate to
Akamai Property management.

Resource Structure
________________________________

An Akamai property is composed of two files:

* ``hostnames.json`` with the host -> edgehostname mapping information
* ``rules.json`` with the CDN delivery configuration rule tree to apply

Both files are completely standard as per the documented schemas and can be
used independently of Bossman through regular API calls or other automation
tools.

Bossman imposes the presence of top-level fields in ``rules.json`` which are not required
by the schema:

* ``productId``
* ``ruleFormat``
* ``groupId``
* ``contractId``

``productId`` and ``ruleFormat`` are required so that Bossman can accurately
validate and version freeze property versions when they are deployed.

``groupId`` and ``contractId`` are required so that Bossman has enough information
to create new properties in the appropriate location.

Resource Configuration
________________________________

.. code-block:: yaml

  resources:
    - module: bossman.plugins.akamai.property
      pattern: akamai/property/{name}
      options:
        edgerc: ~/.edgerc
        section: papi
        switch_key: xyz

The above are the default values, applied even if the ``.bossman`` configuration file is
not present. You only need to configure if you need to depart from the defaults.

``bossman status [glob]``
________________________________

The ``status`` command displays details about *interesting* property versions.

Interesting property versions are either:

* activating, or pending activation on any network
* the latest version
* deployed versions of any HEAD commit of any active branch

In the normal case, property versions are created by bossman and their status line shows:

.. image:: property/normal_status.png

* the property version
* STG, PRD or STG,PRD depending on the activation status (if they are pending activation
  to staging or production, the network trigram is followed by an hourglass)
* the first line of the property version notes, truncated to 40 characters
* a series of git refs to the corresponding commit, coloured green if the version corresponds
  to the latest commit on that branch, or brown if it is behind
* a series of tags pointing at the corresponding commit, coloured blue

It is entirely acceptable to create new versions in the UI without breaking bossman.
If an interesting version was created without using bossman, it will be called out
as **dirty**, and will lack any git ref information to relate it to gitt histtory :

.. image:: property/dirty_status.png


``bossman apply [--force] [glob]``
__________________________________

The ``apply`` command creates a new version for every commit on the current branch.

If the property does not exist, it is created.

Bossman structures property version notes, by encoding:

- the commit message
- metadata about the commit, including

  - the abbreviated commit hash
  - the branches containing the commit
  - the author
  - if applicable, the committer

The purpose is twofold. It improves the quality of property version
notes; if a good git commit message convention is in place, it is
automatically applied to the property version.

It also provides a mechanism for bossman to correlate property versions
with git revisions.

``bossman (pre)release [--rev HEAD] [glob]``
_____________________________________________

prerelease : activates the selected revision and resources to the staging network
release : the same, to the production network

