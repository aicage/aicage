from collections.abc import Callable
from pathlib import Path
from typing import TypeAlias

from aicage.cli_types import ParsedArgs
from aicage.config.context import ConfigContext
from aicage.config.extensions.loader import ExtensionMetadata
from aicage.config.project_config import (
    MOUNT_DOCKER_KEY,
    MOUNT_GITCONFIG_KEY,
    MOUNT_GITROOT_KEY,
    MOUNT_GNUPG_KEY,
    MOUNT_SSH_KEY,
    AgentConfig,
)
from aicage.gpg import has_gpg_keys, resolve_gpg_home
from aicage.runtime._ssh_agent import _has_ssh_keys

from .support.git_support import git_mount_defaults
from .support.mount_prompt import (
    MountSelectionPrompt,
    extension_mount_defaults,
    resolve_mount_prompt_prefs,
)

_ConfirmPreference: TypeAlias = Callable[[], bool]


def apply_mount_preferences(
    context: ConfigContext,
    agent: str,
    parsed: ParsedArgs | None,
    select_mounts: MountSelectionPrompt,
    confirm_persist_docker_socket: _ConfirmPreference,
) -> None:
    agent_cfg = context.project_cfg.agents.setdefault(agent, AgentConfig())
    _apply_git_and_extension_mount_preferences(
        Path(context.project_cfg.path).resolve(),
        agent_cfg,
        context.extensions,
        select_mounts,
    )
    _apply_docker_socket_preference(
        agent_cfg,
        parsed,
        confirm_persist_docker_socket,
    )


def apply_extension_mount_defaults(
    context: ConfigContext,
    agent_cfg: AgentConfig,
) -> None:
    agent_cfg.extension_mounts.update(
        extension_mount_defaults(
            Path(context.project_cfg.path).resolve(),
            agent_cfg,
            context.extensions,
        )
    )


def apply_git_mount_defaults(context: ConfigContext, agent_cfg: AgentConfig) -> None:
    for key in git_mount_defaults(
        Path(context.project_cfg.path).resolve(),
        agent_cfg.mounts,
        override_existing=True,
    ):
        setattr(agent_cfg.mounts, key, True)


def apply_credential_mount_defaults(agent_cfg: AgentConfig) -> None:
    if _ssh_mount_default(agent_cfg):
        agent_cfg.mounts.ssh = True
    if _gnupg_mount_default(agent_cfg):
        agent_cfg.mounts.gnupg = True


def apply_cli_credential_mount_preferences(
    agent_cfg: AgentConfig,
    parsed: ParsedArgs | None,
) -> None:
    if parsed is None:
        return
    if parsed.ssh is not None:
        agent_cfg.mounts.ssh = parsed.ssh
    if parsed.gpg is not None:
        agent_cfg.mounts.gnupg = parsed.gpg


def disable_git_mounts(agent_cfg: AgentConfig) -> None:
    for key in (
        MOUNT_GITCONFIG_KEY,
        MOUNT_GITROOT_KEY,
    ):
        setattr(agent_cfg.mounts, key, False)


def _apply_git_and_extension_mount_preferences(
    project_path: Path,
    agent_cfg: AgentConfig,
    available_extensions: dict[str, ExtensionMetadata],
    select_mounts: MountSelectionPrompt,
) -> None:
    mount_prompt_prefs = resolve_mount_prompt_prefs(
        project_path, agent_cfg, available_extensions, select_mounts
    )
    if mount_prompt_prefs is None:
        return
    for key in (
        MOUNT_GITCONFIG_KEY,
        MOUNT_GITROOT_KEY,
    ):
        if getattr(agent_cfg.mounts, key) is None:
            setattr(agent_cfg.mounts, key, key in mount_prompt_prefs.git_mounts)
    for key in (MOUNT_GNUPG_KEY, MOUNT_SSH_KEY):
        if getattr(agent_cfg.mounts, key) is None:
            setattr(
                agent_cfg.mounts,
                key,
                key in mount_prompt_prefs.credential_mounts,
            )
    agent_cfg.extension_mounts.update(mount_prompt_prefs.extension_mounts)


def _apply_docker_socket_preference(
    agent_cfg: AgentConfig,
    parsed: ParsedArgs | None,
    confirm_persist_docker_socket: _ConfirmPreference,
) -> None:
    if (
        parsed is None
        or not parsed.docker_socket
        or getattr(agent_cfg.mounts, MOUNT_DOCKER_KEY) is not None
    ):
        return
    if confirm_persist_docker_socket():
        setattr(agent_cfg.mounts, MOUNT_DOCKER_KEY, True)


def _ssh_mount_default(agent_cfg: AgentConfig) -> bool:
    return agent_cfg.mounts.ssh is None and _has_ssh_keys()


def _gnupg_mount_default(agent_cfg: AgentConfig) -> bool:
    return (
        agent_cfg.mounts.gnupg is None
        and has_gpg_keys()
        and resolve_gpg_home() is not None
    )
