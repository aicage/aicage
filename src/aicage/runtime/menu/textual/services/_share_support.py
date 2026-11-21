from pathlib import Path

from aicage.config.extensions.loader import ExtensionMetadata
from aicage.config.project_config import (
    MOUNT_GITCONFIG_KEY,
    MOUNT_GITROOT_KEY,
    MOUNT_GNUPG_KEY,
    MOUNT_SSH_KEY,
    AgentConfig,
)
from aicage.config.run_config_draft import RunConfigDraft
from aicage.runtime._errors import RuntimeExecutionError
from aicage.runtime.docker_args.support.git_support import (
    resolve_git_config_path,
    resolve_git_root,
    resolve_gpg_home,
    resolve_ssh_dir,
    uses_ssh_remotes,
)
from aicage.runtime.docker_args.support.signing import (
    is_commit_signing_enabled,
    resolve_signing_format,
)
from aicage.runtime.mounts.shares import (
    ShareSpec,
    merge_share_values,
    resolve_share_specs,
)

from .._models import BuiltInShareSource, BuiltInShareValue
from .._mount_display import extension_label, git_support_label


def normalize_shares_from_editor(
    draft: RunConfigDraft, raw_shares: list[str]
) -> list[str]:
    try:
        return merge_share_values(raw_shares, [], draft.project_path)[0]
    except RuntimeExecutionError:
        raise
    except Exception as exc:
        raise RuntimeExecutionError(str(exc)) from exc


def built_in_share_values(
    draft: RunConfigDraft,
    available_extensions: dict[str, ExtensionMetadata],
) -> list[BuiltInShareValue]:
    mounts_cfg = draft.effective_agent_cfg.mounts
    inherited_mounts = draft.inherited_project_cfg.agents.get(
        draft.agent, AgentConfig()
    ).mounts
    local_mounts = draft.agent_cfg.mounts
    project_path = draft.project_path
    built_in_shares: list[BuiltInShareValue] = []

    git_config = resolve_git_config_path()
    if git_config and git_config.exists():
        built_in_shares.append(
            BuiltInShareValue(
                source=BuiltInShareSource.GIT_SUPPORT,
                key=MOUNT_GITCONFIG_KEY,
                label=git_support_label(MOUNT_GITCONFIG_KEY),
                path=str(git_config),
                persisted=mounts_cfg.gitconfig,
                enabled=_built_in_share_enabled(mounts_cfg.gitconfig),
                inherited=_is_inherited_mount(
                    local_mounts.gitconfig, inherited_mounts.gitconfig
                ),
            )
        )

    git_root = resolve_git_root(project_path)
    if git_root and git_root != project_path:
        built_in_shares.append(
            BuiltInShareValue(
                source=BuiltInShareSource.GIT_SUPPORT,
                key=MOUNT_GITROOT_KEY,
                label=git_support_label(MOUNT_GITROOT_KEY),
                path=str(git_root),
                persisted=mounts_cfg.gitroot,
                enabled=_built_in_share_enabled(mounts_cfg.gitroot),
                inherited=_is_inherited_mount(
                    local_mounts.gitroot, inherited_mounts.gitroot
                ),
            )
        )

    signing_enabled = is_commit_signing_enabled(project_path)
    signing_format = resolve_signing_format(project_path) if signing_enabled else None
    ssh_needed = (signing_enabled and signing_format == "ssh") or uses_ssh_remotes(
        project_path
    )
    if ssh_needed:
        ssh_dir = resolve_ssh_dir()
        if ssh_dir.exists():
            built_in_shares.append(
                BuiltInShareValue(
                    source=BuiltInShareSource.GIT_SUPPORT,
                    key=MOUNT_SSH_KEY,
                    label=git_support_label(MOUNT_SSH_KEY),
                    path=str(ssh_dir),
                    persisted=mounts_cfg.ssh,
                    enabled=_built_in_share_enabled(mounts_cfg.ssh),
                    inherited=_is_inherited_mount(
                        local_mounts.ssh, inherited_mounts.ssh
                    ),
                )
            )

    needs_gnupg = signing_enabled and signing_format != "ssh"
    if needs_gnupg:
        gpg_home = resolve_gpg_home()
        if gpg_home and gpg_home.exists():
            built_in_shares.append(
                BuiltInShareValue(
                    source=BuiltInShareSource.GIT_SUPPORT,
                    key=MOUNT_GNUPG_KEY,
                    label=git_support_label(MOUNT_GNUPG_KEY),
                    path=str(gpg_home),
                    persisted=mounts_cfg.gnupg,
                    enabled=_built_in_share_enabled(mounts_cfg.gnupg),
                    inherited=_is_inherited_mount(
                        local_mounts.gnupg, inherited_mounts.gnupg
                    ),
                )
            )

    built_in_shares.extend(
        _extension_share_values(draft, project_path, available_extensions)
    )
    return built_in_shares


def _extension_share_values(
    draft: RunConfigDraft,
    project_path: Path,
    available_extensions: dict[str, ExtensionMetadata],
) -> list[BuiltInShareValue]:
    items: list[BuiltInShareValue] = []
    agent_cfg = draft.effective_agent_cfg
    inherited_agent_cfg = draft.inherited_project_cfg.agents.get(
        draft.agent, AgentConfig()
    )
    for extension_id in agent_cfg.extensions:
        extension = available_extensions.get(extension_id)
        if extension is None or not extension.shares:
            continue
        specs = resolve_share_specs(extension.shares, project_path)
        if not specs:
            continue
        persisted = agent_cfg.extension_mounts.get(extension_id)
        row_keys = _extension_row_keys(extension_id, specs)
        for spec, row_key in zip(specs, row_keys, strict=True):
            items.append(
                BuiltInShareValue(
                    source=BuiltInShareSource.EXTENSION,
                    key=extension_id,
                    label=extension_label(extension_id),
                    path=_format_share_value(spec),
                    persisted=persisted,
                    enabled=_built_in_share_enabled(persisted),
                    row_key=row_key,
                    inherited=(
                        extension_id in inherited_agent_cfg.extensions
                        and extension_id not in draft.agent_cfg.extension_mounts
                        and persisted is not False
                    ),
                )
            )
    return items


def _extension_row_keys(extension_id: str, specs: list[ShareSpec]) -> list[str | None]:
    if len(specs) == 1:
        return [None]
    return [f"{extension_id}:{_format_share_value(spec)}" for spec in specs]


def _format_share_value(spec: ShareSpec) -> str:
    host_value = str(spec.host_path)
    return f"{host_value}:ro" if spec.read_only else host_value


def _built_in_share_enabled(persisted: bool | None) -> bool:
    if persisted is not None:
        return persisted
    return True


def _is_inherited_mount(local: bool | None, inherited: bool | None) -> bool:
    return local is None and inherited is True
