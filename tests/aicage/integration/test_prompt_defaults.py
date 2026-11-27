import subprocess
from pathlib import Path

import pytest

from aicage.config.config_store import SettingsStore
from aicage.config.project_config import AgentConfig, _AgentMounts, _ProjectConfig
from aicage.paths import container_project_path

from ._helpers import require_integration, run_cli_pty, setup_workspace

pytestmark = pytest.mark.integration


def test_none_uses_default_mount_selection_without_saving(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    require_integration()
    workspace, env = setup_workspace(monkeypatch, tmp_path, "codex")
    project_dir = workspace / "project"
    project_dir.mkdir()
    _init_git_repo(workspace)
    _write_global_gitconfig(Path(env["HOME"]))
    _save_project_config(project_dir, mounts=_AgentMounts())

    exit_code, output = run_cli_pty(
        ["--menu", "none", "--dry-run", "codex"],
        env=env,
        cwd=project_dir,
    )

    assert exit_code == 0, output
    assert "Enable Git support in the container by mounting:" not in output
    assert (
        "Select mounts (comma-separated numbers) [all, default on Enter]:" not in output
    )
    gitconfig = Path(env["HOME"]) / ".gitconfig"
    assert (
        f"--mount type=bind,src={gitconfig.as_posix()},"
        f"dst={container_project_path(gitconfig)}" in output
    )
    assert (
        f"--mount type=bind,src={workspace.as_posix()},"
        f"dst={container_project_path(workspace)}" in output
    )
    agent_cfg = SettingsStore().load_project(project_dir).agents["codex"]
    assert agent_cfg.mounts.gitconfig is None
    assert agent_cfg.mounts.gitroot is None

    # An explicit CLI preference overrides saved mount settings for this run.
    _save_project_config(
        project_dir,
        mounts=_AgentMounts(gitconfig=False, gitroot=False),
    )
    exit_code, output = run_cli_pty(
        ["--menu", "none", "--dry-run", "--git", "codex"],
        env=env,
        cwd=project_dir,
    )

    assert exit_code == 0, output
    assert (
        f"--mount type=bind,src={gitconfig.as_posix()},"
        f"dst={container_project_path(gitconfig)}" in output
    )
    assert (
        f"--mount type=bind,src={workspace.as_posix()},"
        f"dst={container_project_path(workspace)}" in output
    )


def _write_global_gitconfig(home_dir: Path) -> None:
    home_dir.mkdir(parents=True, exist_ok=True)
    gitconfig = home_dir / ".gitconfig"
    gitconfig.write_text(
        "\n".join(
            [
                "[user]",
                "  name = Integration Test",
                "  email = integration@example.com",
            ]
        ),
        encoding="utf-8",
    )


def _init_git_repo(repo_root: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Integration Test"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "integration@example.com"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )


def _save_project_config(project_dir: Path, mounts: _AgentMounts) -> None:
    agent_cfg = AgentConfig(base="ubuntu")
    agent_cfg.mounts = mounts
    SettingsStore().save_project(
        project_dir,
        _ProjectConfig(
            path=str(project_dir),
            agents={"codex": agent_cfg},
        ),
    )
