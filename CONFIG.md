# Configuration

## Locations

- Global config: packaged `config/config.yaml`
- Project config: `~/.aicage/projects/<sha256>.yaml`
- `aicage --config info` prints the current project config path and contents (`print` is an alias).
- `aicage --config remove` removes the current project config file.
- `aicage --config remove <agent>` removes only one agent entry from the current project config.

Project config filenames are the SHA-256 digest of the resolved project path string.

Project config is normally created and updated through the `aicage` menu UI rather than edited by hand.

## Global config schema

`config/config.yaml` is packaged with `aicage` and read on startup.

```yaml
image_registry: string
image_registry_api_url: string
image_registry_api_token_url: string
image_repository: string
default_image_base: string
```

| Key                            | Type   | Presence | Description                                        |
|--------------------------------|--------|----------|----------------------------------------------------|
| `image_registry`               | string | Always   | Registry host used for image pulls.                |
| `image_registry_api_url`       | string | Always   | Registry API base URL for discovery/auth.          |
| `image_registry_api_token_url` | string | Always   | Token endpoint used to request registry access.    |
| `image_repository`             | string | Always   | Image repository name (without tag).               |
| `default_image_base`           | string | Always   | Default base when selecting an image for an agent. |

## Project config schema

`~/.aicage/projects/<sha256>.yaml` stores per-project agent settings.

```yaml
path: string
agents:
  <agent>:
    base: string
    docker_args: string
    image_ref: string
    extensions: [string]
    shares: [string]
    extension_mounts:
      <extension>: bool
    mounts:
      gitconfig: bool
      gitroot: bool
      gnupg: bool
      ssh: bool
      docker: bool
```

| Key              | Type   | Presence | Description                      |
|------------------|--------|----------|----------------------------------|
| `path`           | string | Always   | Absolute project path.           |
| `agents`         | map    | Always   | Per-agent configuration.         |
| `agents.<agent>` | map    | Always   | Agent config schema (see below). |

## Agent config schema

Used under `agents.<agent>` in the project config.

| Key                | Type   | Presence | Description                                               |
|--------------------|--------|----------|-----------------------------------------------------------|
| `base`             | string | Always   | Image base to use for this agent in this project.         |
| `docker_args`      | string | Optional | Persisted `docker run` args for this agent.               |
| `image_ref`        | string | Optional | Selected image ref (prebuilt or extended).                |
| `extensions`       | list   | Optional | Ordered list of selected extensions for this agent.       |
| `shares`           | list   | Optional | Persisted share mounts (`HOST` or `HOST:ro`).             |
| `extension_mounts` | map    | Optional | Persisted on/off choices for extension-defined mounts.    |
| `mounts`           | map    | Optional | Host resource mount preferences.                          |
| `mounts.gitconfig` | bool   | Optional | Mount the host Git config file.                           |
| `mounts.gitroot`   | bool   | Optional | Mount the detected Git repository root.                   |
| `mounts.gnupg`     | bool   | Optional | Make host GnuPG credentials available through its socket. |
| `mounts.ssh`       | bool   | Optional | Make host SSH credentials available through its socket.   |
| `mounts.docker`    | bool   | Optional | Mount `/run/docker.sock` into the container.              |
