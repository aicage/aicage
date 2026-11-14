from pathlib import Path

import pytest

from aicage.config.config_store import SettingsStore
from aicage.config.project_config import AgentConfig, _ProjectConfig
from aicage.constants import DEFAULT_EXTENDED_IMAGE_NAME
from aicage.paths import container_project_path

from ._helpers import (
    copy_marker_extension_sample,
    custom_extensions_dir,
    marker_shared_extension_dir,
    require_integration,
    run_cli_pty,
    setup_workspace,
)

pytestmark = pytest.mark.integration


def test_global_config_inherits_shares_extensions_and_docker_args(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    require_integration()
    workspace, env = setup_workspace(monkeypatch, tmp_path, "copilot")
    global_share_dir = tmp_path / "global-share"
    local_share_dir = tmp_path / "local-share"
    global_share_dir.mkdir()
    local_share_dir.mkdir()
    marker_shared_extension_dir(Path(env["HOME"])).mkdir(parents=True, exist_ok=True)
    copy_marker_extension_sample(custom_extensions_dir() / "marker")
    store = SettingsStore()
    store.save_global(
        _ProjectConfig(
            path="/",
            agents={
                "copilot": AgentConfig(
                    docker_args=(
                        "--env AICAGE_ENTRYPOINT_CMD=bash "
                        "--env GLOBAL_CONFIG_VALUE=global"
                    ),
                    image_ref=f"{DEFAULT_EXTENDED_IMAGE_NAME}:copilot-ubuntu-marker",
                    extensions=["marker"],
                    extension_mounts={"marker": True},
                    shares=[str(global_share_dir)],
                )
            },
        )
    )
    project_cfg = store.load_project(workspace)
    project_cfg.agents["copilot"].docker_args = "--env LOCAL_CONFIG_VALUE=local"
    project_cfg.agents["copilot"].shares = [str(local_share_dir)]
    store.save_project(workspace, project_cfg)
    global_container_path = container_project_path(global_share_dir).as_posix()
    local_container_path = container_project_path(local_share_dir).as_posix()

    exit_code, output = run_cli_pty(
        [
            "--menu",
            "none",
            "copilot",
            "-lc",
            "test -f /usr/local/share/aicage-extensions/marker.txt "
            f"&& test -d {global_container_path} "
            f"&& test -d {local_container_path} "
            '&& test "$GLOBAL_CONFIG_VALUE" = global '
            '&& test "$LOCAL_CONFIG_VALUE" = local',
        ],
        env=env,
        cwd=workspace,
    )

    assert exit_code == 0, output


def test_tree_config_inherits_shares_extensions_and_docker_args(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    require_integration()
    workspace, env = setup_workspace(monkeypatch, tmp_path, "copilot")
    tree_share_dir = tmp_path / "tree-share"
    local_share_dir = tmp_path / "local-share"
    tree_share_dir.mkdir()
    local_share_dir.mkdir()
    marker_shared_extension_dir(Path(env["HOME"])).mkdir(parents=True, exist_ok=True)
    copy_marker_extension_sample(custom_extensions_dir() / "marker")
    store = SettingsStore()
    store.save_tree(
        workspace.parent,
        _ProjectConfig(
            path=str(workspace.parent),
            agents={
                "copilot": AgentConfig(
                    docker_args=(
                        "--env AICAGE_ENTRYPOINT_CMD=bash "
                        "--env INHERITED_CONFIG_VALUE=inherited"
                    ),
                    image_ref=f"{DEFAULT_EXTENDED_IMAGE_NAME}:copilot-ubuntu-marker",
                    extensions=["marker"],
                    extension_mounts={"marker": True},
                    shares=[str(tree_share_dir)],
                )
            },
        ),
    )
    project_cfg = store.load_project(workspace)
    project_cfg.agents["copilot"].docker_args = "--env LOCAL_CONFIG_VALUE=local"
    project_cfg.agents["copilot"].shares = [str(local_share_dir)]
    store.save_project(workspace, project_cfg)
    tree_container_path = container_project_path(tree_share_dir).as_posix()
    local_container_path = container_project_path(local_share_dir).as_posix()

    exit_code, output = run_cli_pty(
        [
            "--menu",
            "none",
            "copilot",
            "-lc",
            "test -f /usr/local/share/aicage-extensions/marker.txt "
            f"&& test -d {tree_container_path} "
            f"&& test -d {local_container_path} "
            '&& test "$INHERITED_CONFIG_VALUE" = inherited '
            '&& test "$LOCAL_CONFIG_VALUE" = local',
        ],
        env=env,
        cwd=workspace,
    )

    assert exit_code == 0, output
