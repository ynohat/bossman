.. _install:

Install
============================

Requirements
____________________________

Bossman requires Python >=3.8 and git >=2.3.10.

.. topic:: Windows

   Bossman should just about run on Windows, but support as it is will be limited.
   Extra dependencies may be required (pay close attention to the output on the
   console when installing via pip).

   **It is highly recommended to use either the Windows Subsystem for Linux or Docker
   when running bossman on windows**.

   The Windows Subsystem for Windows will provide a much smoother than native, but
   do pay close attention to the warnings on the console.

   In both cases (native or WSL), it is strongly recommended to install the `Windows
   Terminal <https://docs.microsoft.com/en-us/windows/terminal>`_. The default terminal
   font does not support all the glyphs used by bossman to convey resource status information.

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
      -v ~/.ssh/id_rsa:/home/bossman/.ssh/id_rsa:ro \
      -v $PWD:/work \
      -v ~/.edgerc:/bossman/.edgerc ynohat/bossman version

- ``-t`` is required to allocate a pseudo-terminal
- ``-e TERM=xterm-256color`` gets rich colour output, which is necessary in particular for making the best use of ``bossman status``
- ``-v ~/.ssh/id_rsa:/home/bossman/.ssh/id_rsa`` mounts your SSH private key into the container; see notes below
- ``-v $PWD:/work`` mounts the current working directory to ``/work`` which is the working directory in the container
- ``-v ~/.edgerc:/home/bossman/.edgerc`` mounts the Akamai credential file in the appropriate location for bossman to find them
- ``ynohat/bossman`` references the Docker repository, however you may wish to `target a specific tag <https://hub.docker.com/repository/docker/ynohat/bossman/tags?page=1&ordering=last_updated>`_.

It is recommended to create a shell alias to avoid typing the above repeatedly!

.. topic:: about mounting your SSH key

   Bossman needs to interact with the git remotes, over SSH. Ideally, we would forward the SSH agent socket
   to docker, but I am failing to get this to work on Mac (and maybe Windows as well). There seems to be
   an issue with SSH agent socket forwarding when docker is running inside a hypervisor.
   
   As a result, mounting the private key is the only way I can propose for now, along with assurances that
   bossman will not attempt to steal these credentials.
   
   I cannot however extend the same guarantee to bossman's dependencies.
   
   If you choose to go forward with mounting your private key as suggested, please make sure you mount the
   key that you have setup in the git remote, of course.

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
