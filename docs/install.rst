.. _install:

Install
============================

Requirements
____________________________

Bossman requires Python 3.8 and git 2.3.10.

Installing Locally
____________________________

.. code-block:: bash

   python3 -m pip install bossman

Using Docker
____________________________

Bossman provides public docker images which can be convenient if the above requirements
are hard to meet.

.. code-block:: bash

   docker run -t --rm \
      -e TERM=xterm-256color \
      -v $PWD:/work \
      -v ~/.edgerc:/bossman/.edgerc ynohat/bossman version

- ``-t`` is required to allocate a pseudo-terminal
- ``-e TERM=xterm-256color`` gets rich colour output, which is necessary in particular for making the best use of ``bossman status``
- ``-v $PWD:/work`` mounts the current working directory to ``/work`` which is the working directory in the container
- ``-v ~/.edgerc:/bossman/.edgerc`` mounts the Akamai credential file in the appropriate location for bossman to find them
- ``ynohat/bossman`` references the Docker repository, however you may wish to `target a specific tag <https://hub.docker.com/repository/docker/ynohat/bossman/tags?page=1&ordering=last_updated>`_.

It is recommended to create a shell alias to avoid typing the above repeatedly!

**Important** when using docker, the git ``user.name`` and ``user.email`` are not set globally.
Make sure you set them locally in the repository configuration:

.. code-block:: bash

   git config --local user.name "Jane DOE"
   git config --local user.email "Jane.DOE@acme.org"

The docker image also comes with a few other tools that go well with bossman, in particular:

- ``jq`` and ``git``
- ``jsonnet`` and ``jsonnetfmt`` in support of `the Jsonnet templating language <https://jsonnet.org>`_
- The ``akamai`` command, along with the ``akamai jsonnet`` plugin which makes it easier to work with Akamai configuration as Jsonnet
- ``httpie`` and the ``httpie-edgegrid`` authentication plugin
