from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from aicage.config.extensions.loader import ExtensionMetadata
from aicage.config.project_config import MOUNT_GNUPG_KEY, MOUNT_SSH_KEY, AgentConfig
from aicage.gpg import has_gpg_keys, resolve_gpg_home
from aicage.paths import HOST_SSH_DIR
from aicage.runtime._ssh_agent import _has_ssh_keys
from aicage.runtime.mounts.shares import ShareSpec, resolve_share_specs

from .git_support import _git_support_prompt_items


@dataclass(frozen=True)
class _MountPromptItem:
    key: str
    description: str


@dataclass(frozen=True)
class _MountSelectionRequest:
    git_items: list[_MountPromptItem]
    credential_items: list[_MountPromptItem]
    extension_items: list[_MountPromptItem]


MountSelectionPrompt = Callable[[_MountSelectionRequest], list[str]]


@dataclass(frozen=True)
class _MountPromptPrefs:
    git_mounts: set[str]
    credential_mounts: set[str]
    extension_mounts: dict[str, bool]


def resolve_mount_prompt_prefs(
    project_path: Path,
    agent_cfg: AgentConfig,
    available_extensions: dict[str, ExtensionMetadata],
    select_mounts: MountSelectionPrompt,
) -> _MountPromptPrefs | None:
    git_items = [
        _MountPromptItem(key, description)
        for key, description in _git_support_prompt_items(
            project_path, agent_cfg.mounts
        )
    ]
    credential_items = _credential_mount_prompt_items(agent_cfg)
    extension_items = _extension_mount_prompt_items(
        project_path,
        agent_cfg.extensions,
        agent_cfg.extension_mounts,
        available_extensions,
    )
    if not git_items and not credential_items and not extension_items:
        return None

    selected = set(
        select_mounts(
            _MountSelectionRequest(git_items, credential_items, extension_items)
        )
    )
    return _MountPromptPrefs(
        git_mounts={item.key for item in git_items if item.key in selected},
        credential_mounts={
            item.key for item in credential_items if item.key in selected
        },
        extension_mounts={item.key: item.key in selected for item in extension_items},
    )


def select_all_mounts(request: _MountSelectionRequest) -> list[str]:
    return [
        item.key
        for item in [
            *request.git_items,
            *request.credential_items,
            *request.extension_items,
        ]
    ]


def _extension_mount_prompt_items(
    project_path: Path,
    selected_extensions: list[str],
    extension_mounts: dict[str, bool],
    available_extensions: dict[str, ExtensionMetadata],
) -> list[_MountPromptItem]:
    items: list[_MountPromptItem] = []
    for extension_id in selected_extensions:
        if extension_id in extension_mounts:
            continue
        extension = available_extensions.get(extension_id)
        if extension is None or not extension.shares:
            continue
        share_specs = resolve_share_specs(extension.shares, project_path)
        share_values = ", ".join(_format_share_value(spec) for spec in share_specs)
        items.append(
            _MountPromptItem(
                key=extension_id,
                description=f"Extension {extension_id} shares: {share_values}",
            )
        )
    return items


def extension_mount_defaults(
    project_path: Path,
    agent_cfg: AgentConfig,
    available_extensions: dict[str, ExtensionMetadata],
) -> dict[str, bool]:
    return {
        item.key: True
        for item in _extension_mount_prompt_items(
            project_path,
            agent_cfg.extensions,
            agent_cfg.extension_mounts,
            available_extensions,
        )
    }


def _format_share_value(spec: ShareSpec) -> str:
    host_value = str(spec.host_path)
    return f"{host_value}:ro" if spec.read_only else host_value


def _credential_mount_prompt_items(agent_cfg: AgentConfig) -> list[_MountPromptItem]:
    items: list[_MountPromptItem] = []
    if agent_cfg.mounts.ssh is None and _has_ssh_keys():
        items.append(_MountPromptItem(MOUNT_SSH_KEY, f"SSH agent: {HOST_SSH_DIR}"))
    if agent_cfg.mounts.gnupg is None and has_gpg_keys():
        gpg_home = resolve_gpg_home()
        if gpg_home is not None:
            items.append(_MountPromptItem(MOUNT_GNUPG_KEY, f"GnuPG agent: {gpg_home}"))
    return items
