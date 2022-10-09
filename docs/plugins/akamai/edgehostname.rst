.. _plugins_akamai_property:

Akamai EdgeHostname
================================

This page provides reference information about how bossman commands relate to
Akamai Edge Hostname management.

Resource Configuration
________________________________

.. code-block:: yaml

  resources:
    - module: bossman.plugins.akamai.edgehostname
      pattern: akamai/edgehostname/{name}.json
      options:
        edgerc: ~/.edgerc
        section: default
        #env_prefix: ""
        #account_key: xyz

The above are the default values, applied even if the ``.bossman`` configuration file is
not present. You only need to configure if you need to depart from the defaults.

With these defaults, Bossman will look for files matching ``akamai/edgehostname/{name}.json`` and treat
them as Akamai Edge Hostname definitions. The ``{name}`` placeholder is arbitrary and doesn't have any
particular meaning, although it is recommended to use the Edge Hostname itself since it is guaranteed
to be unique.

It is also possible to pass values from the environment. Please refer to :ref:`plugins_akamai_property`
for more information on this topic.

The next section details the structure of the resource, the files Bossman expects to find
within the property configuration folder.

Resource Structure
________________________________

An Akamai EdgeHostname is composed of a single JSON file with the following structure:

.. code-block:: json

  {
    "contractId": "ctr_C-1ED34DY",
    "groupId": "grp_101216",
    "edgeHostname": {
      "domainPrefix": "example.com",
      "domainSuffix": "edgekey.net",
      "ipVersionBehavior": "IPV6_COMPLIANCE",
      "productId": "SPM",
      "secureNetwork": "ENHANCED_TLS",
      "certEnrollmentId": 144436
    }
  }

The documentation for the `Create a new edge hostname PAPI endpoint <https://techdocs.akamai.com/property-mgr/reference/post-edgehostnames>`_
describes the fields.

Note that:

* ``certEnrollmentId`` should only be provided if ``secureNetwork`` is ``ENHANCED_TLS``
* Only the fields in the JSON example above are supported by bossman

``bossman status [-e|--exact-match] [glob*]``
__________________________________________________________________________________________________

Unimplemented.

``bossman apply [--force] [--dry-run] [--since=commit] [-e|--exact-match] [glob*]``
__________________________________________________________________________________________________

Will create the Edge Hostname if required.
Any subsequent commit affecting the Edge Hostname JSON file might cause bossman to output an apply result,
but in reality it will have no effect.

``bossman (pre)release [--rev HEAD] [-e|--exact-match] [glob*]``
_______________________________________________________________________

These commands have no effect since an Edge Hostname is not a versioned resource.
Once applied, the changes are effective on all networks.
