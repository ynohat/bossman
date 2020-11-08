Philosophy
===========

When `announcing Waypoint <https://www.hashicorp.com/blog/announcing-waypoint>`_, Hashicorp defined the
application lifecycle as having three main stages.

* Build : convert application source code to an artifact
* Deploy : push the built artifact to a platform
* Release : make the artifact, on the platform, available to its public

This is a simplified, but useful view.

When managing Akamai configuration artifacts, you are:

* Building JSON configuration from a template
* Deploying JSON configuration to a new version of an Akamai object (property, cloudlet policy etc...)
* Releasing to the staging network or the production network

Bossman is not opinionated about the build process. It concerns itself mainly with deployment and release
of configuration artifacts that are built through some other mechanism.
