from pathlib import Path
from typing import Protocol

from aicage.config.project_config import (
    MOUNT_GITCONFIG_KEY,
    MOUNT_GITROOT_KEY,
)

from ._exec import capture_stdout


class _MountPrefs(Protocol):
    gitconfig: bool | None
    gitroot: bool | None


def resolve_git_config_path() -> Path | None:
    stdout = capture_stdout(["git", "config", "--global", "--show-origin", "--list"])
    if not stdout:
        return None
    for line in stdout.splitlines():
        if not line.startswith("file:"):
            continue
        parts = line[5:].split()
        if not parts:
            continue
        return Path(parts[0]).expanduser()
    return None


def resolve_git_root(project_path: Path) -> Path | None:
    superproject = _resolve_git_path(
        ["git", "rev-parse", "--show-superproject-working-tree"],
        project_path,
    )
    if superproject:
        return superproject
    return _resolve_git_path(["git", "rev-parse", "--show-toplevel"], project_path)


def _resolve_git_path(command: list[str], project_path: Path) -> Path | None:
    stdout = capture_stdout(command, cwd=project_path)
    if not stdout:
        return None
    value = stdout.strip()
    if not value:
        return None
    return Path(value).resolve()


def _git_support_prompt_items(
    project_path: Path,
    mounts_cfg: _MountPrefs,
) -> list[tuple[str, str]]:
    git_items: list[tuple[str, str]] = []

    git_config = resolve_git_config_path()
    if git_config and git_config.exists() and mounts_cfg.gitconfig is None:
        git_items.append(
            (
                MOUNT_GITCONFIG_KEY,
                f"Git config (name/email): {git_config}",
            )
        )

    git_root = resolve_git_root(project_path)
    if git_root and git_root != project_path and mounts_cfg.gitroot is None:
        git_items.append(
            (
                MOUNT_GITROOT_KEY,
                f"Git root (repository access): {git_root}",
            )
        )

    return git_items


def git_mount_defaults(
    project_path: Path,
    mounts_cfg: _MountPrefs,
    *,
    override_existing: bool = False,
) -> set[str]:
    """Return detected Git mounts that should be enabled for this run.

    An explicit ``--git`` request must take precedence over a saved ``false``
    value.  Ordinary default selection, by contrast, leaves an explicit saved
    value alone.
    """
    return {
        key
        for key in detected_git_mounts(project_path)
        if override_existing or getattr(mounts_cfg, key) is None
    }


def detected_git_mounts(project_path: Path) -> set[str]:
    return {
        key
        for key, _description in _git_support_prompt_items(
            project_path, _UnsetMountPrefs()
        )
    }


class _UnsetMountPrefs:
    gitconfig: bool | None = None
    gitroot: bool | None = None
