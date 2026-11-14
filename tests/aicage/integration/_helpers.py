import os
import select
import stat
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from shutil import copytree
from typing import Any, cast

import pytest

from aicage import paths as paths_module
from aicage.config import config_store as config_store_module
from aicage.config.config_store import SettingsStore
from aicage.config.project_config import AgentConfig, _AgentMounts, _ProjectConfig
from aicage.constants import DEFAULT_EXTENDED_IMAGE_NAME
from aicage.docker.query import (
    get_local_repo_digest_for_repo,
    get_local_rootfs_layers,
    local_image_exists,
)
from aicage.docker.refs import repository_from_image_ref
from aicage.registry.agent_build._store import BuildRecord, BuildStore
from aicage.registry.digest.remote_digest import get_remote_digest

if sys.platform == "win32":
    pty = None
else:
    import pty


def run_cli_pty(
    args: list[str],
    env: dict[str, str],
    cwd: Path,
    *,
    input_data: str | None = None,
) -> tuple[int, str]:
    if sys.platform == "win32":
        process = _spawn_winpty_process(
            [sys.executable, "-m", "aicage", *args],
            env,
            str(cwd),
        )
        win_output_chunks: list[str] = []

        def _read_output() -> None:
            while True:
                try:
                    chunk = process.read()
                except EOFError:
                    break
                if not chunk:
                    break
                win_output_chunks.append(chunk)

        reader = threading.Thread(target=_read_output, daemon=True)
        reader.start()
        if input_data:
            process.write(input_data)
        process.wait()
        reader.join(timeout=1.0)
        exit_status = process.exitstatus
        if exit_status is None:
            exit_status = process.wait()
        return cast(int, exit_status), "".join(win_output_chunks)

    assert pty is not None
    master_fd, slave_fd = pty.openpty()
    process = subprocess.Popen(
        [sys.executable, "-m", "aicage", *args],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=cwd,
        env=env,
        close_fds=True,
    )
    os.close(slave_fd)

    if input_data:
        os.write(master_fd, input_data.encode())

    posix_output_chunks: list[bytes] = []
    while True:
        read_ready, _, _ = select.select([master_fd], [], [], 0.2)
        if master_fd in read_ready:
            try:
                data = os.read(master_fd, 4096)
            except OSError:
                data = b""
            if data:
                posix_output_chunks.append(data)
            elif process.poll() is not None:
                break
        elif process.poll() is not None:
            break

    process.wait()
    os.close(master_fd)
    output = b"".join(posix_output_chunks).decode(errors="replace")
    return process.returncode, output


def _spawn_winpty_process(cmd: list[str], env: dict[str, str], cwd: str) -> Any:
    winpty_module = import_module("winpty")
    pty_process_cls = winpty_module.PtyProcess
    return pty_process_cls.spawn(cmd, env=env, cwd=cwd)


def require_integration() -> None:
    if not os.environ.get("AICAGE_RUN_INTEGRATION"):
        pytest.skip("Set AICAGE_RUN_INTEGRATION=1 to run integration tests.")


def require_proxy_integration() -> None:
    if not os.environ.get("AICAGE_RUN_PROXY_INTEGRATION"):
        pytest.skip(
            "Set AICAGE_RUN_PROXY_INTEGRATION=1 to run proxy integration tests."
        )


def setup_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    agent_name: str,
    *,
    docker_args: str | None = None,
) -> tuple[Path, dict[str, str]]:
    home_dir = Path.home().resolve()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    workspace = workspace.resolve()
    monkeypatch.chdir(workspace)
    projects_dir = home_dir / ".aicage/projects"
    trees_dir = home_dir / ".aicage/config/trees"
    global_config_path = home_dir / ".aicage/config/global.yml"
    custom_root_dir = home_dir / ".aicage-custom"
    custom_bases_path = custom_root_dir / "base-images"
    custom_agents_path = custom_root_dir / "agents"
    custom_extensions_path = custom_root_dir / "extensions"
    image_build_dir = home_dir / ".aicage/state/image/build"
    extended_build_dir = home_dir / ".aicage/state/image-extended/build"
    base_image_build_dir = home_dir / ".aicage/state/base-image/build"
    version_check_dir = home_dir / ".aicage/state/agent/version-check/state"
    monkeypatch.setattr(paths_module, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(config_store_module, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(paths_module, "TREES_DIR", trees_dir)
    monkeypatch.setattr(config_store_module, "TREES_DIR", trees_dir)
    monkeypatch.setattr(paths_module, "GLOBAL_CONFIG_PATH", global_config_path)
    monkeypatch.setattr(config_store_module, "GLOBAL_CONFIG_PATH", global_config_path)
    monkeypatch.setattr(paths_module, "CUSTOM_BASES_DIR", custom_bases_path)
    monkeypatch.setattr(paths_module, "CUSTOM_AGENTS_DIR", custom_agents_path)
    monkeypatch.setattr(paths_module, "CUSTOM_EXTENSIONS_DIR", custom_extensions_path)
    monkeypatch.setattr(paths_module, "IMAGE_BUILD_STATE_DIR", image_build_dir)
    monkeypatch.setattr(
        paths_module, "IMAGE_EXTENDED_BUILD_STATE_DIR", extended_build_dir
    )
    monkeypatch.setattr(
        paths_module, "BASE_IMAGE_BUILD_STATE_DIR", base_image_build_dir
    )
    monkeypatch.setattr(
        paths_module, "AGENT_VERSION_CHECK_STATE_DIR", version_check_dir
    )

    store = SettingsStore()
    store.projects_dir = projects_dir
    agent_cfg = AgentConfig(base="ubuntu")
    agent_cfg.mounts = _AgentMounts(
        gitconfig=False,
        gnupg=False,
        ssh=False,
        docker=False,
    )
    if docker_args:
        agent_cfg.docker_args = docker_args
    project_cfg = _ProjectConfig(
        path=str(workspace),
        agents={agent_name: agent_cfg},
    )
    store.save_project(workspace, project_cfg)

    return workspace, build_cli_env(home_dir)


def setup_marker_extension_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    agent_name: str,
) -> tuple[Path, dict[str, str], str, Path]:
    require_integration()
    workspace, env = setup_workspace(
        monkeypatch,
        tmp_path,
        agent_name,
        docker_args="--env AICAGE_ENTRYPOINT_CMD=bash",
    )
    share_dir = marker_shared_extension_dir(Path(env["HOME"]))
    share_dir.mkdir(parents=True, exist_ok=True)
    extension_dir = custom_extensions_dir() / "marker"
    extension_dir.parent.mkdir(parents=True, exist_ok=True)
    copy_marker_extension_sample(extension_dir)
    image_ref = f"{DEFAULT_EXTENDED_IMAGE_NAME}:{agent_name}-ubuntu-marker"
    store = SettingsStore()
    project_cfg = store.load_project(workspace)
    agent_cfg = project_cfg.agents[agent_name]
    agent_cfg.base = "ubuntu"
    agent_cfg.docker_args = "--env AICAGE_ENTRYPOINT_CMD=bash"
    agent_cfg.image_ref = image_ref
    agent_cfg.extensions = ["marker"]
    agent_cfg.extension_mounts["marker"] = True
    store.save_project(workspace, project_cfg)
    return workspace, env, image_ref, share_dir


def run_agent_version(env: dict[str, str], workspace: Path, agent_name: str) -> None:
    exit_code, output = run_cli_pty(
        ["--menu", "none", agent_name, "--version"],
        env=env,
        cwd=workspace,
    )
    assert exit_code == 0, output
    output_lines = [line.strip() for line in output.splitlines() if line.strip()]
    assert output_lines
    assert output_lines[-1]


def assert_marker_extension_ready(
    env: dict[str, str],
    workspace: Path,
    agent_name: str,
    *,
    share_dir: Path | None = None,
) -> None:
    exit_code, output = run_cli_pty(
        [
            "--menu",
            "none",
            agent_name,
            "-lc",
            "test -f /usr/local/share/aicage-extensions/marker.txt",
        ],
        env=env,
        cwd=workspace,
    )
    assert exit_code == 0, output

    if share_dir is not None:
        container_path = paths_module.container_project_path(share_dir).as_posix()
        exit_code, output = run_cli_pty(
            ["--menu", "none", agent_name, "-lc", f"test -d {container_path}"],
            env=env,
            cwd=workspace,
        )
        assert exit_code == 0, output


def force_record_agent_version(
    store: BuildStore,
    record: BuildRecord,
    *,
    agent_version: str,
) -> None:
    updated = BuildRecord(
        agent=record.agent,
        base=record.base,
        agent_version=agent_version,
        base_image=record.base_image,
        image_ref=record.image_ref,
        built_at=record.built_at,
        image_id=record.image_id,
    )
    store.save(updated)


def replace_with_dummy_image(image_ref: str) -> str:
    subprocess.run(
        [
            "docker",
            "import",
            "-",
            image_ref,
        ],
        check=True,
        capture_output=True,
        input=b"",
    )
    repository = repository_from_image_ref(image_ref)
    digest = get_local_repo_digest_for_repo(image_ref, repository)
    if digest is not None:
        return f"{repository}@{digest}"

    inspect = subprocess.run(
        ["docker", "image", "inspect", image_ref, "--format", "{{.Id}}"],
        check=True,
        capture_output=True,
        text=True,
    )
    image_id = inspect.stdout.strip()
    assert image_id.startswith("sha256:")
    assert local_image_exists(image_id)
    return image_id


def assert_old_image_replaced(old_image_ref: str, image_ref: str) -> None:
    if old_image_ref.startswith("sha256:"):
        inspect = subprocess.run(
            ["docker", "image", "inspect", image_ref, "--format", "{{.Id}}"],
            check=True,
            capture_output=True,
            text=True,
        )
        updated_id = inspect.stdout.strip()
        assert updated_id != old_image_ref
        return
    assert not local_image_exists(old_image_ref)


def get_last_rootfs_layer(image_ref: str) -> str:
    layers = get_local_rootfs_layers(image_ref)
    assert layers is not None
    return layers[-1]


def resolve_remote_digest_ref(image_ref: str) -> str:
    if "@sha256:" in image_ref:
        return image_ref
    repository = repository_from_image_ref(image_ref)
    digest = get_remote_digest(image_ref)
    assert digest is not None
    return f"{repository}@{digest}"


def assert_rootfs_layer_present(layer: str, image_ref: str) -> None:
    layers = get_local_rootfs_layers(image_ref)
    assert layers is not None
    assert layer in layers


@contextmanager
def keep_pulled_image_last_rootfs_layer(image_ref: str) -> Iterator[str]:
    assert "@sha256:" in image_ref
    subprocess.run(
        ["docker", "pull", image_ref],
        check=True,
        capture_output=True,
    )
    try:
        yield get_last_rootfs_layer(image_ref)
    finally:
        subprocess.run(
            ["docker", "image", "rm", image_ref],
            check=False,
            capture_output=True,
        )


def build_cli_env(home_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    if sys.platform == "win32":
        home_str = str(home_dir)
        drive, tail = os.path.splitdrive(home_str)
        env["USERPROFILE"] = home_str
        if drive:
            env["HOMEDRIVE"] = drive
            env["HOMEPATH"] = tail or "\\"
    repo_root = Path(__file__).resolve().parents[3]
    env["PYTHONPATH"] = str(repo_root / "src")
    for key in list(env):
        if key == "AGENT":
            env.pop(key, None)
            continue
        if key.startswith("AICAGE_") and key != "AICAGE_RUN_INTEGRATION":
            env.pop(key, None)
    return env


def _custom_root_dir() -> Path:
    return Path(os.path.expanduser("~/.aicage-custom"))


def custom_agents_dir() -> Path:
    return _custom_root_dir() / "agents"


def copy_forge_sample(target_dir: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    source_dir = repo_root / "doc/sample/custom/agents/forge"
    copytree(source_dir, target_dir, dirs_exist_ok=True)
    _make_executable(target_dir / "install.sh")
    _make_executable(target_dir / "version.sh")


def setup_custom_bash_agent(target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "agent.yml").write_text(
        "\n".join(
            [
                "agent_path:",
                "  directories:",
                "    - ~/.aicage-test-dir",
                "  files:",
                "    - ~/.aicage-test-file",
                "    - ~/.aicage-test-file.backup",
                "agent_full_name: Bash",
                "agent_homepage: https://example.invalid",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (target_dir / "install.sh").write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (target_dir / "version.sh").write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "bash"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def custom_extensions_dir() -> Path:
    return _custom_root_dir() / "extensions"


def custom_bases_dir() -> Path:
    return _custom_root_dir() / "base-images"


def marker_shared_extension_dir(home_dir: Path) -> Path:
    return home_dir / ".aicage-test-share"


def copy_custom_base_sample(sample_name: str, target_dir: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    source_dir = repo_root / "doc/sample/custom/base-images" / sample_name
    copytree(source_dir, target_dir, dirs_exist_ok=True)


def copy_marker_extension_sample(target_dir: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    source_dir = repo_root / "doc/sample/custom/extensions/marker"
    copytree(source_dir, target_dir, dirs_exist_ok=True)
    for script in (target_dir / "scripts").glob("*.sh"):
        _make_executable(script)


def copy_marker_dockerfile_extension_sample(target_dir: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    source_dir = repo_root / "doc/sample/custom/extensions/marker-dockerfile"
    copytree(source_dir, target_dir, dirs_exist_ok=True)


def _make_executable(path: Path) -> None:
    current = path.stat().st_mode
    path.chmod(current | stat.S_IEXEC)
