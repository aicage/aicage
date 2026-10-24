# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.5.3] - 2026-10-24

### Added

- Added global and directory-tree configuration scopes, allowing agent settings to be inherited and reused across
  projects.
- Added `--base`, `--extension`, and `--git` options for configuring non-interactive and integration-driven runs.

### Changed

- Removed the line-based `--menu simple` setup flow. Use the default `--menu ui` configuration UI, or `--menu none`
  with CLI options for non-interactive runs.
- `--config remove` now requires an agent name, limiting removal to one agent configuration at a time.
- Python 3.11 is now the minimum supported version; Python 3.10 is no longer supported.

### Fixed

- Ignore stale extended-image references when selecting an image.
- Preserve pending image-update confirmations when extensions require an image build.
- Support Docker named-pipe (`npipe://`) endpoints when passing Docker access into a container on Windows.

### Quality

- Expanded automated validation across Windows, proxy, image, and live ACP/OpenRouter scenarios.

### Documentation

- Documented configuration scopes and refreshed configuration UI screenshots.

## [1.5.2] - 2026-10-10

### Added

- GitHub releases now include the built wheel and source distribution with a signed checksum manifest.

## [1.5.1] - 2026-10-10

### Added

- Added `aicage-amp`, `aicage-claude`, and `aicage-codex` launcher commands for ACP bridges used by Amp CLI,
  Claude Code, and Codex CLI in IDEs.

### Changed

- Moved Kimi Code CLI from the built-in agent set to custom samples because its ACP integration currently fails in
  JetBrains.
- Removed Gemini CLI from the built-in agent set because its host credentials cannot be shared reliably with a
  container.

### Documentation

- Reworked the README around IDE setup, first-run authentication, supported agents, project configuration, and
  customization.

## [1.5.0] - 2026-10-08

### Added

- Added ACP (Agent Client Protocol) capable agents:
  - Agents: Amp CLI, Auggie CLI, Kimi Code CLI, Kiro CLI, and Mistral Vibe CLI.
- Bundled shim scripts for using agents Amp CLI, Claude Code, and Codex CLI in IDEs through external ACP bridges.

### Changed

- Moved agents without ACP support agents out of the built-in agent set. They do not support ACP. Use custom agent
  definitions for them.
  - Agents: Antigravity CLI and Crush

## [1.4.20] - 2026-09-21

### Changed

- Refreshed metadata on generated agent images.
- Updated dependencies

## [1.4.19] - 2026-09-04

### Changed

- `aicage` now skips setup menus automatically when stdin is not a TTY, so IDE plugins no longer need to pass
  `--menu none`. Interactive terminal runs continue to open the setup UI by default.

## [1.4.18] - 2026-09-03

### Changed

- Docker TTY allocation is now detected automatically. `aicage` uses `docker run -it` when stdin is a TTY and
  `docker run -i` for non-TTY callers such as IDE plugins, so the previous `--stdio` option is no longer needed.

## [1.4.17] - 2026-09-03

### Changed

- Custom agent images now remove installer artifacts and package caches after installation, reducing image size.

## [1.4.16] - 2026-08-27

### Changed

- Project configuration files now indent list items for easier reading.

### Documentation

- Added guidance for using aicage from JetBrains agent plugins.

## [1.4.15] - 2026-08-26

### Added

- Added `--stdio` to run agents with stdin but without a Docker TTY, for SDK and protocol use.

### Changed

- Operational setup messages now use stderr, keeping stdout available for agent and protocol output.
- Arguments after the agent name are now forwarded verbatim to the agent.
- `--menu none` now applies Docker arguments, shares, and mount choices only to the current run instead of saving them
  to the project configuration.

### Fixed

- Local agent images that have been replaced or become stale are now rebuilt before use.

## [1.4.14] - 2026-08-25

### Fixed

- Local agent image update prompts now name the remote base image that will be pulled instead of the locally built
  agent image.

### Internal

- Renamed the internal selected agent image reference field to avoid confusing it with `aicage-image-base` images.

## [1.4.13] - 2026-08-25

### Fixed

- Claude agent images on Arch Linux now work around the Claude 2.1.242/2.1.243 startup crash with glibc 2.44.

### Changed

- Extension documentation now describes `shares` entries for mounting existing host paths.

### Internal

- Updated CI linting configuration, and development dependencies.

## [1.4.12] - 2026-08-11

### Changed

- Removed agent clipboard sharing. Agents that write to the clipboard generally support OSC 52 directly, which is the
  preferred path instead.

## [1.4.11] - 2026-07-28

### Changed

- Image setup now routes pull, verification, and local-build preparation through a shared reporting path so setup
  progress is surfaced more consistently across the UI and non-UI flows.

### Internal

- Refactored Docker support modules and setup reporting internals, and cleaned up test package scaffolding.
- Simplified the internal agent-image setup planning API.

## [1.4.10] - 2026-07-27

### Fixed

- The setup overview now shows the correct extension count after previously configured extensions have been removed.

## [1.4.9] - 2026-07-27

### Changed

- Build shell-based extensions in one batch when creating extended images, which reduces extension build overhead and
  speeds up image preparation for users who enable multiple shell-based extensions.

## [1.4.8] - 2026-07-25

### Fixed

- Canceling image setup from the UI now stops active setup work more reliably, including on Windows.

### Changed

- Added an OSC 52 clipboard fallback so clipboard sharing now works beyond native Linux Wayland/X11 host
  integration, including non-Linux hosts and Linux terminal sessions without display-server clipboard access.
- Clipboard sharing is now available from the setup overview on every host.

## [1.4.7] - 2026-07-23

### Changed

- Added a built-in clipboard host integration toggle that mounts the required Linux Wayland or X11 host resources for
  containerized agents when enabled.
- Extended the Textual host access flow so clipboard integration is offered only on Linux hosts and the confirmation
  dialog shows the concrete clipboard socket and environment exposure that will be persisted.

## [1.4.6] - 2026-07-23

### Changed

- Refined the README wording around first-run prompts, Windows usage, macOS support caveats, and container visibility
  boundaries.

### Internal

- Bumped the pip development dependency group.

## [1.4.5] - 2026-07-22

### Fixed

- Missing extensions no longer abort the run in `--menu none` mode; unavailable extensions are automatically removed
  with a log warning and the run continues.
- Unknown agent names now list the available agents in the error message.

### Changed

- Separated Textual config and execution into independent apps, so image pull/build progress displays in a dedicated
  screen rather than being inlined in the config overview.
- Renamed `--menu textual` to `--menu ui`; `simple` and `none` are unchanged.
- Image update confirmation is now resolved at the interaction layer instead of inside decision logic, allowing each
  menu mode to handle confirmation consistently.
- The Textual base selection screen now accepts on row click instead of requiring the OK button.
- Tab/Shift+Tab navigation in the Textual extensions screen now cycles between checkboxes and the OK button.

### Internal

- Replaced the global mutable prompt-mode flag with a `RuntimeInteraction` protocol backed by `SimpleInteraction`,
  `TextualInteraction`, and `_NoneInteraction`, giving each menu mode explicit control over default and confirmation
  behavior.
- Renamed prompt modules to private (`_base`, `_confirm`, `_extensions`, `_image_ref`) and removed per-prompt log
  noise.
- Moved Textual screens into `views/` and extracted execution and image-update apps from the monolithic config app.
- Extracted `extended_image_name` into `config.image_refs` to remove inline duplication.
- Injected mount-prompt callables into docker-args resolution to decouple from concrete prompt implementations.
- Tightened module and function visibility across config, docker, and runtime packages.
- Updated README with the Antigravity CLI agent (`agy`).

## [1.4.4] - 2026-07-16

### Fixed

- Fixed the Textual setup view so local image builds no longer start hidden preflight work before progress is shown.

## [1.4.3] - 2026-07-16

### Fixed

- Fixed the Textual setup view so image preparation no longer appears blank before the container starts.

## [1.4.2] - 2026-07-16

### Fixed

- Fixed the default Textual setup flow so pressing `OK` no longer triggers a second image setup pass before the
  container starts.

## [1.4.1] - 2026-07-16

### Fixed

- Fixed the published PyPI package for `1.4.x` releases so `aicage` installs and starts correctly again when
  installed from PyPI.

### Internal

- Added a release smoke test that installs the built wheel and runs `aicage --version` before publishing to PyPI.

## [1.4.0] - 2026-07-16

### Added

- Added a Textual-based configuration UI as the default interactive setup for `aicage <agent>`. It replaces the old
  prompt-by-prompt flow with a single overview where users can review and adjust base image, extensions, bind mounts,
  Docker socket access, and Docker arguments before starting.

### Changed

- Replaced `--yes` with `--menu textual|simple|none` to support the new UI while still allowing the classic
  line-based prompts or a no-menu defaults flow.
- Existing per-project agent configs can now be changed from the interactive UI instead of often requiring config
  removal and a fresh setup.
- Added an inline execution view in the Textual UI so required image pulls and builds report progress before the
  container starts.

## [1.3.4] - 2026-07-11

### Changed

- Adapted the runtime environment passed into `entrypoint.sh` to a simplified contract.
- Added rootless Docker daemon support, including automatic runtime detection and correct Docker endpoint/socket
  handling, so `aicage` can run cleanly in setups that prefer a more locked-down container environment.

## [1.3.3] - 2026-07-10

### Changed

- `aicage` now works correctly from forked repositories by accepting fork-owned image signatures and matching forked
  image source metadata during verification.
- Show a TTY pull progress bar while Docker images download, so large first-time pulls no longer look idle and
  still keep the raw pull event log unchanged.

## [1.3.2] - 2026-07-02

### Changed

- Improved the home-mount refusal message with clearer guidance.

## [1.3.1] - 2026-07-01

### Added

- Added Arch Linux as a built-in base image option on `amd64` hosts.

### Changed

- Base selection now respects per-base CPU architecture support, so incompatible bases are hidden on unsupported
  hosts.
- Custom base definitions now require an `architectures` list in `base.yml` or `base.yaml` using `amd64` and/or
  `arm64`.

## [1.2.5] - 2026-06-05

### Added

- Added the Antigravity CLI agent as `Antigravity` (`agy`).

### Internal

- Synced bundled agent install/version scripts with the current upstream agent images.
- Hardened releases to fail when a pushed tag does not point to a commit on `main`.
- Bumped pinned GitHub Actions and the `ruff` development dependency.

## [1.1.8] - 2026-05-15

### Fixed

- Improved Goose agent image compatibility by installing the required Vulkan loader during agent setup and by
  excluding `node` bases whose bundled glibc is too old for current Goose releases.

### Internal

- Hardened CI to fail workflows that reference GitHub Actions by mutable refs instead of immutable commit digests.
- Bumped development tool versions for `check-jsonschema`, `pyright`, `pymarkdownlnt`, and `ruff`.

## [1.1.1] - 2026-04-28

### Changed

- Prompt before pulling a newer remote `aicage` or `aicage-image-base` image when a local image is already
  available, and show the full image reference in the prompt text.

## [1.1.0] - 2026-04-19

### Changed

- Pass the host timezone into container runs via `TZ`, with host timezone detection split into a dedicated runtime
  module and covered by focused tests.

### Internal

- Bumped `actions/upload-artifact` from `7.0.0` to `7.0.1` in the GitHub Actions integration workflows.

## [1.0.11] - 2026-04-09

### Internal

- Reverted the release workflow package SBOM generation added in `1.0.10`.

## [1.0.10] - 2026-04-09

### Internal

- Generate and upload a CycloneDX SBOM for the built wheel as a separate release artifact.

## [1.0.9] - 2026-04-09

### Changed

- Authenticate release lookups with `GITHUB_TOKEN` when available.

## [1.0.3] - 2026-04-08

### Fixed

- Print a short error message for unexpected CLI exceptions and write the full traceback to the log.

### Changed

- Require expected OCI manifest annotations when verifying official remote `aicage` images.

## [1.0.1] - 2026-03-30

### Changed

- Allow `aicage --config` without an explicit subcommand and treat it as `info`.
- Extensions can now define share mounts.

### Internal

- Switched config schema validation to `jsonschema`.
- Moved repository rule tests into `tests/repo_rules`.

## [1.0.0] - 2026-03-26

### Changed

- Confirmed macOS support by GitHub-hosted integration tests.

## [0.9.48] - 2026-03-24

### Fixed

- Preserve nested child mounts when they override the parent mount access mode, so child `:ro` or read-write
  mounts are no longer dropped when the parent path is also mounted.

## [0.9.42] - 2026-03-19

### Fixed

- Allow verification of images signed by GitHub Actions workflows from any repository in the `aicage` org, not only
  `aicage/github-actions`.

## [0.9.41] - 2026-03-18

### Fixed

- Normalize interactive extension selections to prompt order so the same selected extensions produce the same default
  extended image name regardless of input order.

## [0.9.40] - 2026-03-18

### Fixed

- Allow verification of images produced by `aicage/github-actions` reusable workflows referenced by commit digest, not
  only by `refs/...` identities.

## [0.9.29] - 2026-03-17

### Internal

- Added Dependabot version update configuration and explicit dependency version ranges for runtime and development
  dependencies.
- Pinned GitHub Actions to commit digests and refreshed the GitHub Actions dependency set.
- Split the reusable test suite from the release workflow so pull requests run change validation separately while
  releases remain gated by tests.

## [0.9.28] - 2026-02-27

### Fixed

- After a successful `aicage` self-update, the CLI now restarts with the same arguments so the updated version runs
  immediately in the current invocation.

## [0.9.27] - 2026-02-27

### Changed

- Clarified base image selection prompts to explicitly say that pressing Enter accepts the default selection.

## [0.9.26] - 2026-02-27

### Changed

- Documentation refresh release: updated user-facing `README.md` content and examples (including setup flow and
  screenshots) for improved first-use guidance on PyPI.

## [0.9.25] - 2026-02-27

### Fixed

- Allow mounting `~/.ssh` and `~/.gnupg` together when both are needed (for example SSH remotes plus GPG commit
  signing), instead of treating them as mutually exclusive in Git support mount preference resolution.

## [0.9.24] - 2026-02-26

### Changed

- Mount host paths directly to their target container paths (including paths under host home) instead of routing
  through `/aicage/user-home`.
- Added nested mount de-duplication in Docker mount resolution so parent mounts take precedence over overlapping child
  mounts.

### Internal

- Refactored mount mapping/dedup logic into `runtime.docker_args.resolve._mounts` and kept resolver orchestration
  focused on provider composition.
- Added integration coverage for direct home mounts, parent-path ownership behavior, and nested mount de-duplication.

## [0.9.22] - 2026-02-26

### Changed

- Expanded SSH key mount detection and prompting to cover repositories with SSH Git remotes, not only SSH-based
  commit signing.
- Updated SSH mount prompt/config wording to reflect Git SSH access (push/fetch) in addition to signing.

## [0.9.21] - 2026-02-26

### Added

- Added `-y/--yes` to apply default answers for all prompts in non-interactive runs.

### Changed

- Reworked the Git support mount prompt to allow selecting specific mount targets via comma-separated option numbers,
  with Enter applying the default `all` selection.
- Prompt flows now auto-select defaults without rendering interactive questions when `-y/--yes` is set.
- Default base selection now derives from host Linux distro metadata (`ID` and `ID_LIKE`) and matches against
  available configured bases, including custom base names; fallback remains `ubuntu`.

### Internal

- Updated Git support prompt and resolver unit tests for per-mount selection behavior.
- Added prompt unit coverage for host-aware default-base resolution and prompt default propagation.
- Hardened integration tests against Docker daemon differences where local replacement images may not expose
  `RepoDigests` for the retagged repository, by using replacement-reference-aware assertions.

## [0.9.20] - 2026-02-17

### Added

- Added `--config remove [<agent>]` support to remove a single agent entry from a project's config file without
  deleting the full file.
- Added host proxy env forwarding for image builds and runtime (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`,
  `NO_PROXY`) to improve support behind corporate proxies.

### Changed

- Expanded `--help` output with clearer argument descriptions and behavior notes.
- Clarified `--` separator behavior in help: it is required only when Docker args are present before the agent.
- Improved network failure diagnostics for version and registry checks with structured categories (for example DNS,
  TLS, and proxy auth failures).

### Internal

- Added proxy integration tests and CI coverage.

## [0.9.19] - 2026-02-16

### Fixed

- Allow local agent runs to continue in offline scenarios when remote base digest verification fails but a usable
  local image is already available (local base digest fallback and local final-agent image fallback).
- Added explicit timeouts for host and builder-container agent version checks to prevent offline hangs.
- For local agents, fall back to a cached agent version when host and image-based version checks fail offline, instead
  of hard-exiting.

### Changed

- Centralized timeout constants in `aicage.constants`.
- Split Docker timeouts by operation type: short timeout for local Docker metadata queries, long timeout for image
  pulls, and short timeout for registry JSON lookups.

## [0.9.18] - 2026-02-15

### Added

- Added the `opencode` agent definition (install/version scripts and default config/state directories) synced from
  `aicage-image`.

### Changed

- Custom base rebuild checks now rely on image existence, build record metadata, and source digest changes; they no
  longer use rootfs layer comparison against the `from_image`.
- Simplified base-layer validation flow by making `base_layer_missing` return a boolean directly and centralizing the
  "missing local layer data" warning inside that helper.
- Synced bundled agent definitions with `aicage-image`, including the `goose` config directory updates.

## [0.9.16] - 2026-02-15

### Changed

- Refactored registry build structure into clear packages (`agent_build`, `base_build`, `extension_build`) and moved
  agent version checks under `agent_build.agent_version`.
- Unified agent/base/extension ensure orchestration through a shared build flow helper.
- Aligned build failure semantics so build errors propagate consistently across all three build flows.
- Standardized module and method naming across the build packages for clearer responsibilities.

## [0.9.15] - 2026-02-15

### Fixed

- Keep source image tags after successful local builds (agent images, extension images, and custom base images) so
  subsequent runs can reuse local tag metadata and avoid an unnecessary extra pull.

### Internal

- Updated integration tests around base-layer rebuild flows to assert the retained source-tag behavior.

## [0.9.14] - 2026-02-14

### Changed

- Clean up superseded image digests after `docker run` exits, including cases where cleanup could not happen during
  pull because another process was still using the image.
- Clean up superseded digests after local rebuilds of agent images, extension images, and custom base images.
- Remove source image tags after successful local builds to keep local image tags cleaner while preserving reusable
  layer content.

### Added

- Added integration coverage for image cleanup across pull, run, and local rebuild flows.

### Internal

- Refactored integration tests around cleanup scenarios to use real Docker behavior, unified helpers, and reduced
  duplication.
- Performed follow-up test/code cleanup (visibility alignment, static non-instance tests, fixture reuse, and naming
  cleanups).

## [0.9.11] - 2026-02-05

### Changed

- Switched `agent_path` to explicit `files` and `directories` lists and made it optional in agent definitions.
- Stop creating host paths for `--share` mounts; missing files or directories must exist on the host.

### Added

- Added integration coverage for creating and mounting `agent_path` files and directories for custom agents.

### Fixed

- Print underlying Docker stderr when container startup fails to improve error visibility.

### Internal

- Split `runtime.docker_args` into resolver implementations plus shared support/resolve helpers, and reorganized
  associated tests to match the new package layout.
- Update integration coverage for `agent_path` to use a custom bash agent with a reusable setup helper.

## [0.9.10] - 2026-02-05

### Changed

- Set `AICAGE_WORKSPACE` to the host path in container form, even when the mount is routed through
  `/aicage/user-home`.
- Added `AICAGE_HOME` and `AICAGE_HOST_IS_LINUX` to the entrypoint env contract and removed `AICAGE_USER`.

### Internal

- Updated env/mount tests for the revised entrypoint env contract.

## [0.9.9] - 2026-02-04

### Changed

- Unified mount resolution to map host-home paths into `/aicage/user-home`, keeping container user homes clean.
- Centralized mount/env-var resolution across project, agent config, git, shares, and Docker socket support.

### Fixed

- Improve home-directory mount guard errors to include the offending host path.

### Internal

- Isolate tests from the real host home directory via a temporary test home.

## [0.9.8] - 2026-02-03

### Added

- Added `--share` to mount extra host paths into the container for a single run (supports `:ro`).
- Added Docker CLI helper and tests for running Docker commands.

### Changed

- Use Docker `--mount` instead of `-v/--volume` for `docker run` mounts.

### Internal

- Refactored Docker run helpers and expanded mount tests.
- Updated integration coverage to exercise share mounts and run through `entrypoint.sh` via
  `AICAGE_ENTRYPOINT_CMD`.

## [0.9.7] - 2026-01-29

### Internal

- Release bump to validate update notifications.

## [0.9.6] - 2026-01-29

### Fixed

- Move the update prompt into the shared prompt helpers and default to updating.

## [0.9.5] - 2026-01-29

### Internal

- Release bump to validate update notifications.
- Renamed the release workflow file to `release.yml`.

## [0.9.4] - 2026-01-29

### Added

- Added a startup check that prompts to upgrade when a newer aicage version is available.

## [0.9.3] - 2026-01-29

### Added

- Added `--config remove` to delete the project config.

### Changed

- Renamed the `--config print` action to `--config info` (the old name remains as an alias).

### Documentation

- Highlighted the full wiki docs in the README and updated config command references.

## [0.9.2] - 2026-01-28

### Fixed

- Remove unused image digests after pulling newer versions of AICAGE, base, and cosign images.

### Internal

- Added integration coverage for image digest cleanup after pulls.

## [0.9.1] - 2026-01-28

### Added

- Verify signatures for AICAGE images using pinned digests during pulls and local builds.
- Cache and verify the cosign image digest in CI using the release public key.

### Changed

- Pin base image references to registry digests for local builds.

## [0.9.0] - 2026-01-27

### Documentation

- Added links to the new GitHub wiki for customization, updates, docker args, and debugging guides.

## [0.8.27] - 2026-01-25

### Added

- Added `--version` to the CLI.

### Changed

- Unified Git support prompts (Git config, repo root, and signing keys) into a single flow.
- Prompt to mount the Git repository root when running from a subfolder.
- Renamed internal definition files from `.yaml` to `.yml`.

### Fixed

- Refuse to start when the project path or mounts would expose the host home directory.

## [0.8.22] - 2026-01-22

### Fixed

- Ensure agent config file mounts create files (not directories) on first run.

## [0.8.21] - 2026-01-22

### Added

- Support multiple `agent_path` entries with `/aicage/agent-config` mounts and per-path symlinks in the container.

### Changed

- Agent schemas and definitions now require `agent_path` as a list.
- Agent config resolution now handles existing file paths without suffixes.

## [0.8.20] - 2026-01-21

### Fixed

- Restored `--docker` support for Docker-in-container on Windows.

### Internal

- Centralized host SSH and GnuPG path constants and aligned tests to use them.

## [0.8.18] - 2026-01-20

### Fixed

- Hardened Windows support by normalizing script line endings and execution for extensions, agent version checks,
  and custom base image samples.

## [0.8.17] - 2026-01-15

### Fixed

- Restored the console script import target for the CLI `main` entrypoint.

## [0.8.16] - 2026-01-15

### Added

- Packaged base definitions under `config/base-build/bases/` with per-base `base.yaml` and `base-build.yaml`.
- Shared helper to download release artifacts from `aicage-image`/`aicage-image-base`.

### Changed

- CLI requires a `--` separator before agent args when passing Docker args.
- Runtime selection and image resolution now use `ConfigContext` and `RunConfig.selection` directly.
- Removed `config/images-metadata.yaml` and related schema in favor of base and agent configs.

### Internal

- Consolidated base/agent loaders under `aicage.config.base` and `aicage.config.agent`.
- Tightened module visibility and removed unused `__future__` imports.
- Updated sync scripts and workflows for base-image metadata packaging.

## [0.8.12] - 2026-01-14

### Added

- Integration test coverage for custom bases across built-in and custom agents, including extensions.
- Custom base images documentation in `doc/custom-base-images.md`.

## [0.8.7] - 2026-01-13

### Added

- Custom base image discovery and validation for local base image definitions.
- Local custom base build pipeline with digest lookup and stored metadata.
- Customization samples and Dockerfile examples for custom base images.

### Changed

- Custom directories now live under `~/.aicage-custom`.
- Storage/log paths for custom and local builds are consolidated under the new custom root.
- Custom base metadata loads once per run instead of on every access.
- Global config file removed in favor of constants.

### Internal

- Refactored registry digest helpers and expanded digest coverage.
- Enforced test-structure mapping rules and updated test module names.
- Updated image submodules to the latest revisions.

## [0.8.1] - 2026-01-11

### Added

- Added synced agent build definitions for remote-built agents from `aicage-image`.
- Added sync and schema validation helpers.

### Changed

- Moved config schemas into `config/validation/`.
- CI workflows now sync config and validate schemas via the new scripts.

## [0.8.0] - 2026-01-11

### Changed

- Renamed base image metadata key `root_image` to `from_image` in config and schema data.

## [0.7.6] - 2026-01-11

### Added

- Extension config schema validation for local custom extensions.
- End-user documentation for custom agents in `doc/custom-agents.md`.

### Changed

- Config loading for extensions, custom agents, and images metadata is centralized under `aicage.config`.
- Run config now carries the config context used during image selection and builds.

### Internal

- Split agent-version checks and image-selection logic into focused modules.
- Reworked extension and image-selection tests to mirror the new package structure.
- Added local build ref helpers and registry time/log/sanitize utilities.

## [0.7.5] - 2026-01-10

### Changed

- Extension builds now run as a strict post-step on a guaranteed-local base+agent image.
- Image pull and local build paths now pass explicit image refs instead of copying run configs.

### Internal

- Centralized base-layer checks for local and extended image decisions.
- Simplified pull decisions to return booleans.
- Added a registry-level ensure entrypoint for local image setup.

## [0.7.4] - 2026-01-10

### Changed

- Image pulls now use the Docker SDK with streaming logs.

### Internal

- Increased Docker SDK and registry HTTP timeouts for slow connections.

## [0.7.3] - 2026-01-10

### Changed

- Builder version checks now pre-pull the util image with a log path notice and reuse local images on pull
  failure.

### Internal

- Moved local image existence checks to the Docker SDK client.
- Ran builder version checks via Docker SDK containers.
- Reworked Docker query helpers to use dedicated image reference dataclasses.

## [0.7.2] - 2026-01-09

### Internal

- Centralized Docker interactions under `aicage.docker` and moved run/build/pull/query helpers into it.
- Split extension metadata helpers into `aicage.registry.extensions` and promoted runtime env vars module.
- Added task 16 Docker SDK migration subtasks in `doc/ai/task/16/`.

## [0.7.1] - 2026-01-09

### Changed

- Custom extension directory moved to `~/.aicage/custom/extensions/`.

### Internal

- Added integration test coverage for extensions with local built-in, remote built-in, and local custom agents.

## [0.7.0] - 2026-01-08

### Added

- Local extensions under `~/.aicage/custom/extensions/` with extension metadata, scripts, and optional Dockerfile.
- Extended final images with local config under `~/.aicage/custom/image-extended/`.
- Image selection flow to pick base images or extended images and apply extensions.
- Local build/update pipeline for extended images with build logs and stored metadata.
- End-user documentation for extension authoring and usage.

### Changed

- Project config now stores extended image refs and extension selections per agent.
- Extension build Dockerfiles no longer include `# syntax` directives or unused build args.

### Internal

- Added test coverage for extension discovery, selection, prompts, and extended image build flows.

## [0.6.4] - 2026-01-08

### Changed

- Local builds now validate base image updates by checking base layers in final images, removing stored base digest
  state.

### Internal

- Consolidated YAML path constants and refreshed integration/CI helpers for clearer test and pipeline output.

## [0.6.3] - 2026-01-07

### Fixed

- Accept lowercase registry digest headers when checking for newer remote images.

## [0.6.2] - 2026-01-07

### Added

- Integration test coverage for remote built-in, local built-in, and local custom agent workflows.

### Changed

- Custom agent directory moved to `~/.aicage/custom/agents/`.
- Renamed `--entrypoint` to `--aicage-entrypoint` to avoid collision with Docker.

## [0.6.1] - 2026-01-04

### Fixed

- Synced the packaged Dockerfile with the updated `entrypoint.sh` from `aicage-image`.

## [0.6.0] - 2026-01-03

### Added

- Support custom local agents under `~/.aicage/custom/agent/` with schema validation and local builds.

## [0.5.14] - 2026-01-03

### Changed

- Update image- and agent-metadata from latest `aicage-image` release.

## [0.5.13] - 2026-01-02

### Added

- Added `local_image_repository` config for consistent local image naming.

### Changed

- Custom and non-redistributable agents now use `local_image_repository` for local image refs.

## [0.5.12] - 2026-01-02

### Fixed

- Agent version checks now run with `/bin/bash` on host and in the util image.
- Entrypoint mount tests now reflect the bash-based entrypoint script.

## [0.5.11] - 2026-01-02

### Fixed

- Version checks now default to the published `aicage-image-util:agent-version` tag.

### Changed

- Agent version checks prefer the host toolchain before pulling the util image.

## [0.5.10] - 2026-01-02

### Fixed

- Package now includes the latest images metadata by downloading and packaging it, not just testing it.
- Publish job now pins the package version to the release tag to avoid local-version uploads.

## [0.5.9] - 2026-01-02

### Added

- Shared pull log location for all image pulls.
- Local `scripts/lint.sh` helper for linting and `__all__` checks.
- Coverage for runtime config persistence/version checks and a dynamic `__all__` test.

### Changed

- Docker pull output is now written to logs; CLI prints a single-line pull message with log path.
- CLI internals moved into `aicage/cli/` for clearer separation.

### Refactored

- Split local build logic into smaller modules (plan, digest, runner).
- Split image pull logic into decision and runner helpers.

## [0.5.8] - 2026-01-02

### Added

- Support non-redistributable agents with local final-image builds and update checks.
- Local build pipeline for non-redistributable agents (local image naming, build metadata, and logs).
- Added `image_base_repository` to global config.
- Packaged non-redistributable agent build context under `config/agent-build/`.
- Remote digest queries consolidated for base-image checks.

## [0.4.10] - 2025-12-31

### Added

- Core runtime that pulls and runs published `aicage` images built by `aicage-image` and `aicage-image-base`.

## [0.4.x] - Historical

### Added

- Initial release series: `aicage` CLI + image build/publish tooling via submodules.

## [Planned]

### [0.8.x]

- Custom local base images and full build pipeline for agents and extensions on top.
