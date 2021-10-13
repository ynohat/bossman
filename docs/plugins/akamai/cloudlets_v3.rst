.. _plugins_akamai_cloudlet_v3:

Akamai Cloudlets (v3)
================================

This page provides reference information about how bossman commands relate to
Akamai Cloudlets management.

.. warning::
    Only the cloudlets supported by the Akamai Cloudlets v3 API are currently supported by this
    plugin. The complete list of supported cloudlets is on `developer.akamai.com <https://developer.akamai.com/api/web_performance/cloudlets/v3.html#cloudletsthatusethisapi>`_.
    Please feel free to open a GitHub issue if your use case requires another Cloudlet.

Resource Configuration
________________________________

.. code-block:: yaml

  resources:
    - module: bossman.plugins.akamai.cloudlet_v3
      pattern: akamai/cloudlets/{name}
      options:
        edgerc: ~/.edgerc
        section: default
        #env_prefix: ""
        #switch_key: xyz

The above are the default values, applied even if the ``.bossman`` configuration file is
not present. You only need to configure if you need to depart from the defaults.

With these defaults, Bossman will look for folders under ``akamai/cloudlet`` and treat
them as Akamai Property configurations. The ``{name}`` placeholder is required and defines
the name of the property to be managed.

.. warning::
    The name may only have letters, numbers, and underscores. This is stricter than may be allowed by
    your filesystem implementation.

It is also possible to pass values from the environment. Please refer to :ref:`plugins_akamai_property`
for more information on this topic.

The next section details the structure of the resource, the files Bossman expects to find
within the property configuration folder.

Resource Structure
________________________________

An Akamai cloudlet is composed of one file, ``policy.json``, which describes both the necessary
metadata for managing the policy, and for managing the rules that apply when the cloudlet is
invoked.

The schema of this file is custom to ``bossman`` and cannot be reused in a direct API call.

.. code-block:: json

  {
    "cloudletType": "ER",
    "description": "Main redirect rules",
    "groupId": 200128,
    "matchRules": [
        {
          "matchURL": "/images/*",
          "name": "Redirect images",
          "redirectURL": "/static/images4/*",
          "statusCode": 302,
          "type": "erMatchRule",
          "useIncomingQueryString": true,
          "useRelativeUrl": "relative_url"
        }
    ]
  }

The following top-level fields belong to `the Policy data object <https://developer.akamai.com/api/web_performance/cloudlets/v3.html#policy>`_, you will find their
documentation there:

* ``cloudletType``
* ``description``
* ``groupId``

The ``matchRules`` top-level field defines the actual logic and is specified on the `Policy Version data object <https://developer.akamai.com/api/web_performance/cloudlets/v3.html#version>`_.

Usage Notes
________________________________

Because cloudlets have a very similar lifecycle to Akamai properties, please refer to :ref:`plugins_akamai_property` for any details about
how the different Bossman commands relate to Cloudlets.
