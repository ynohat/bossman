# Bossman

Automation framework, motivated by Akamai configuration management, but theoretically extensible.

## Concept

The purpose of bossman is to allow _resources_ to be declared as code. It has a plugin architecture,
allowing more resource types to be added.

Resources are materialized locally by a set of configuration artifacts stored in a filesystem, and
remotely by ways that depend on the resource type.

Bossman tracks both the local revisions in git and the remote revisions of the resources and keeps
them in sync.

It is inspired by Terraform, but does not aim to replace it.

## Motivation

We have Terraform - why Bossman?

Simply because it is quicker to write a bossman resource type, allowing quick support for features,
at the expense of all the good things in Terraform.

## Am I stuck with Bossman?

No. Bossman is only concerned with (simple) orchestration. It is very unopinionated about configuration
representation. If you have a piece of valid configuration for a resource type, it is valid
for Bossman. Bossman also does not store local state.

## Status

This is alpha software. It is useful, but at your own risk.

## Install

```bash
pip install bossman
```

## Compatibility

Should work on all platforms, but not extensively tested.

## Usage

### Prerequisites

A git repository containing configuration artifacts.

### Configuration file

Within your infrastructure project, create a `.bossman` file.

This is a YAML file that defines the resource types and how they resolve
to the configuration files in the repository. A simple example:

```yaml
resources:
  - module: bossman.plugins.akamai.property
    pattern: akamai/property/{name}/
```

With the above, bossman will start managing Akamai property configurations stored
in folders matching `akamai/property/{name}`.

### Execution

```bash
bossman status # list resources and their status
bossman log # like git log, but resource rather than file centric
bossman apply # apply local changes to the infrastructure
```

## Resource Types

### `bossman.plugins.akamai.property`

Manages Akamai delivery configurations.

```yaml
resources:
    # Required: python module name
  - module: bossman.plugins.akamai.property
    # Required: pattern matching config paths to this resource type
    pattern: akamai/property/{name}/
    # Optional: plugin specific parameters
    options:
      edgerc: /path/to/edgerc
      section: papi
      #switch_key: xyz
```

## Extending

The extension mechanism should be fairly straightforward.

* Write a python module exposing a `ResourceType` class
* `ResourceType` should extend `bossman.abc.ResourceTypeABC`
* Make the module available on the python search path

Assuming you have a module called `acme.bossman.resource.foo`,
exposing a `ResourceType` class, you should then be able
to declare it in `.bossman` like this:

```yaml
resources:
  - module: acme.bossman.resource.foo
    pattern: acme/foo/{frobble}/{widget}.json
```

The pattern path parameters are specific to resource types,
Bossman doesn't care about them and should be used to enhance
extension functionaliy.

The project is not stable, so the extension mechanism is likely
to change without warning.

