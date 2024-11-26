# Manage last admin of a room

This module uses third-party rules callbacks from Synapse's module interface to identify
when the last admin of a room leaves it, and when they make default level as admin or only moderator as admin.

As with other modules using third-party rules callbacks, it is recommended that this
module is only used in a closed federation in which every server has this module
configured the same way.

This module requires Synapse v1.39.0 or later.


## Config

Add the following to your Synapse config:

```yaml
modules:
  - module: manage_last_admin.ManageLastAdmin
    config:
      # Optional: if set to true, when the last admin in a room leaves it, the module will
      # try to promote any moderator (or user with the highest power level) as admin. In
      # this mode, it will only set default level as admin on the room if it can't find any user to promote.
      # Defaults to false.
      promote_moderators: false
      # List of domains (server names) that can't be invited to rooms if the
      # "restricted" rule is set. Users from those server will never be granted admin by this module.
      # Defaults to an empty list.
      domains_forbidden_when_restricted: []
```

## Development and Testing

This repository uses `tox` to run tests.

### Tests

This repository uses `unittest` to run the tests located in the `tests`
directory. They can be ran with `tox -e tests`.
