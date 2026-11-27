import os
import re
import shlex
import subprocess
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from aicage.config.config_store import SettingsStore
from aicage.paths import container_project_path
from aicage.runtime.credential_agent import _resources
from aicage.runtime.credential_agent._resource_models import _CredentialProtocol

from ._helpers import (
    require_integration,
    run_cli_pty,
    setup_workspace,
    temporary_test_root,
)

pytestmark = pytest.mark.integration


def _ssh_resource_name() -> str:
    return _resources._resources([_CredentialProtocol.SSH])[0].container_name


def test_ssh_agent_is_available_in_container(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    if sys.platform != "linux":
        pytest.skip("Direct host SSH forwarding is Linux-only.")
    require_integration()
    initial_cwd = Path.cwd()
    temp_root = Path(__file__).resolve().parents[4] / ".aicage-test-tmp"
    temp_root.mkdir(exist_ok=True)
    with temporary_test_root(temp_root) as root:
        home = root / "home"
        try:
            home.mkdir()
            _set_home(monkeypatch, home)
            workspace, env = setup_workspace(
                monkeypatch,
                tmp_path,
                "copilot",
                workspace_path=root / "workspace",
            )
            subprocess.run(
                ["git", "init", "--quiet"],
                cwd=workspace,
                check=True,
                capture_output=True,
            )
            keys = _configure_ssh_keys(home)
            (workspace / "allowed_signers").write_text(
                f"aicage {keys.public_keys[0]}\n", encoding="utf-8"
            )
            _enable_ssh_mount(workspace)

            with _ssh_agent(root / "agent.sock") as agent_env:
                env.update(agent_env)
                command = _ssh_target_command(keys)
                exit_code, output = run_cli_pty(
                    [
                        "--menu",
                        "none",
                        "-e",
                        "AICAGE_ENTRYPOINT_CMD=bash",
                        "--",
                        "copilot",
                        "-lc",
                        command,
                    ],
                    env=env,
                    cwd=workspace,
                )

                assert exit_code == 0, output
                identities = subprocess.run(
                    ["ssh-add", "-L"],
                    check=True,
                    capture_output=True,
                    text=True,
                    env={**os.environ, **agent_env},
                ).stdout
                for public_key in keys.public_keys:
                    assert public_key in identities
                _assert_ssh_authentication(workspace, env, keys.public_paths[0])
        finally:
            monkeypatch.chdir(initial_cwd)


def test_ssh_agent_is_available_in_container_through_sidecar(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    require_integration()
    initial_cwd = Path.cwd()
    temp_root = Path(__file__).resolve().parents[4] / ".aicage-test-tmp"
    temp_root.mkdir(exist_ok=True)
    with temporary_test_root(temp_root) as root:
        home = root / "home"
        try:
            home.mkdir()
            _set_home(monkeypatch, home)
            workspace, env = setup_workspace(
                monkeypatch,
                tmp_path,
                "copilot",
                workspace_path=root / "workspace",
            )
            subprocess.run(
                ["git", "init", "--quiet"],
                cwd=workspace,
                check=True,
                capture_output=True,
            )
            keys = _configure_ssh_keys(home)
            (workspace / "allowed_signers").write_text(
                f"aicage {keys.public_keys[0]}\n", encoding="utf-8"
            )
            env.pop("SSH_AUTH_SOCK", None)
            command = _ssh_target_command(keys)

            # The CLI preference overrides the saved SSH mount setting, which is off.
            exit_code, output = run_cli_pty(
                [
                    "--menu",
                    "none",
                    "--ssh",
                    "-e",
                    "AICAGE_ENTRYPOINT_CMD=bash",
                    "--",
                    "copilot",
                    "-lc",
                    command,
                ],
                env=env,
                cwd=workspace,
            )

            assert exit_code == 0, output
            for key in keys.private_paths:
                _assert_ssh_sidecar_has_key(key)
            _assert_ssh_authentication(
                workspace, env, keys.public_paths[0], ssh_override=True
            )
            subprocess.run(
                ["docker", "stop", _ssh_resource_name()],
                check=True,
                capture_output=True,
            )
            exit_code, output = run_cli_pty(
                [
                    "--menu",
                    "none",
                    "--ssh",
                    "-e",
                    "AICAGE_ENTRYPOINT_CMD=bash",
                    "--",
                    "copilot",
                    "-lc",
                    command,
                ],
                env=env,
                cwd=workspace,
            )
            assert exit_code == 0, output
        finally:
            monkeypatch.chdir(initial_cwd)


def test_ssh_sidecar_removes_deleted_host_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    require_integration()
    initial_cwd = Path.cwd()
    temp_root = Path(__file__).resolve().parents[4] / ".aicage-test-tmp"
    temp_root.mkdir(exist_ok=True)
    with temporary_test_root(temp_root) as root:
        home = root / "home"
        home.mkdir()
        try:
            _set_home(monkeypatch, home)
            keys = _configure_ssh_keys(home)
            identities = [_ssh_public_identity(path) for path in keys.private_paths]
            workspace, env = setup_workspace(
                monkeypatch,
                tmp_path,
                "copilot",
                workspace_path=root / "workspace",
            )
            _enable_ssh_mount(workspace)
            env.pop("SSH_AUTH_SOCK", None)

            _run_credential_setup(workspace, env)
            for identity in identities:
                _assert_ssh_sidecar_has_identity(identity)
            for key in [*keys.private_paths, *keys.public_paths]:
                key.unlink()
            _run_credential_setup(workspace, env)
            for identity in identities:
                _assert_ssh_sidecar_lacks_identity(identity)
        finally:
            monkeypatch.chdir(initial_cwd)


def test_protected_ssh_sidecar_key_does_not_block_noninteractive_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    require_integration()
    initial_cwd = Path.cwd()
    temp_root = Path(__file__).resolve().parents[4] / ".aicage-test-tmp"
    temp_root.mkdir(exist_ok=True)
    with temporary_test_root(temp_root) as root:
        home = root / "home"
        home.mkdir()
        try:
            _set_home(monkeypatch, home)
            key = _configure_protected_ssh_key(home)
            workspace, env = setup_workspace(
                monkeypatch,
                tmp_path,
                "copilot",
                workspace_path=root / "workspace",
            )
            _enable_ssh_mount(workspace)
            env.pop("SSH_AUTH_SOCK", None)

            _run_credential_setup(workspace, env)

            _assert_ssh_sidecar_lacks_identity(_ssh_public_identity(key))
        finally:
            monkeypatch.chdir(initial_cwd)


class _SshKeys:
    def __init__(self, private_paths: list[Path]) -> None:
        self.private_paths = private_paths
        self.public_paths = [
            path.with_name(f"{path.name}.pub") for path in private_paths
        ]
        self.public_keys = [
            " ".join(path.read_text(encoding="utf-8").split()[:2])
            for path in self.public_paths
        ]


def _ssh_target_command(keys: _SshKeys) -> str:
    return " && ".join(
        [
            *[
                f"ssh-add -L | grep -F -- {shlex.quote(public_key)}"
                for public_key in keys.public_keys
            ],
            *[
                f"test -r {shlex.quote(container_project_path(path).as_posix())}"
                for path in keys.public_paths
            ],
            *[
                f"! test -e {shlex.quote(container_project_path(path).as_posix())}"
                for path in keys.private_paths
            ],
            "printf '%s\\n' signed > signing-message",
            "rm -f signing-message.sig",
            (
                "ssh-keygen -Y sign -U "
                f"-f {shlex.quote(container_project_path(keys.public_paths[0]).as_posix())} "
                "-n aicage signing-message"
            ),
            (
                "ssh-keygen -Y verify -f allowed_signers -I aicage "
                "-n aicage -s signing-message.sig < signing-message"
            ),
        ]
    )


def _configure_ssh_keys(home: Path) -> _SshKeys:
    ssh_dir = home / ".ssh"
    ssh_dir.mkdir()
    default_key = ssh_dir / "id_ed25519"
    configured_key = ssh_dir / "keys" / "work"
    configured_key.parent.mkdir()
    for key in (default_key, configured_key):
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
            check=True,
            capture_output=True,
        )
    included_config = ssh_dir / "config.d" / "work"
    included_config.parent.mkdir()
    included_config.write_text(
        f"Host work.example\n    IdentityFile {configured_key}\n",
        encoding="utf-8",
    )
    (ssh_dir / "config").write_text("Include config.d/*\n", encoding="utf-8")
    return _SshKeys([default_key, configured_key])


def _configure_protected_ssh_key(home: Path) -> Path:
    ssh_dir = home / ".ssh"
    ssh_dir.mkdir()
    key = ssh_dir / "id_ed25519"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "secret", "-f", str(key)],
        check=True,
        capture_output=True,
    )
    return key


def _assert_ssh_sidecar_has_key(key: Path) -> None:
    _assert_ssh_sidecar_has_identity(_ssh_public_identity(key))


def _ssh_public_identity(key: Path) -> str:
    return " ".join(key.with_name(f"{key.name}.pub").read_text().split()[:2])


def _assert_ssh_sidecar_has_identity(identity: str) -> None:
    result = subprocess.run(
        [
            "docker",
            "exec",
            _ssh_resource_name(),
            "sh",
            "-c",
            "SSH_AUTH_SOCK=/run/credential-agent/ssh-agent.sock ssh-add -L",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert identity in result.stdout


def _assert_ssh_sidecar_lacks_identity(identity: str) -> None:
    result = subprocess.run(
        [
            "docker",
            "exec",
            _ssh_resource_name(),
            "credential-agent",
            "ssh",
            "list",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert identity not in result.stdout


def _enable_ssh_mount(workspace: Path) -> None:
    store = SettingsStore()
    project_cfg = store.load_project(workspace)
    project_cfg.agents["copilot"].mounts.ssh = True
    store.save_project(workspace, project_cfg)


def _run_credential_setup(workspace: Path, env: dict[str, str]) -> None:
    exit_code, output = run_cli_pty(
        [
            "--menu",
            "none",
            "-e",
            "AICAGE_ENTRYPOINT_CMD=bash",
            "--",
            "copilot",
            "-lc",
            "true",
        ],
        env=env,
        cwd=workspace,
    )
    assert exit_code == 0, output


def _assert_ssh_authentication(
    workspace: Path,
    env: dict[str, str],
    public_key: Path,
    *,
    ssh_override: bool = False,
) -> None:
    image_name = "aicage-integration-sshd"
    container_name = f"aicage-integration-sshd-{uuid.uuid4().hex}"
    authorized_keys = workspace / "authorized_keys"
    store = SettingsStore()
    project_cfg = store.load_project(workspace)
    previous_docker_args = project_cfg.agents["copilot"].docker_args
    authorized_keys.write_text(public_key.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(
        [
            "docker",
            "build",
            "--tag",
            image_name,
            "--file",
            str(Path(__file__).with_name("sshd") / "Dockerfile"),
            str(Path(__file__).resolve().parents[3]),
        ],
        check=True,
        capture_output=True,
    )
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--detach",
                "--name",
                container_name,
                "--mount",
                f"type=bind,src={authorized_keys},dst=/authorized_keys,readonly",
                image_name,
            ],
            check=True,
            capture_output=True,
        )
        project_cfg = store.load_project(workspace)
        project_cfg.agents["copilot"].docker_args = (
            f"--network container:{container_name}"
        )
        store.save_project(workspace, project_cfg)
        exit_code, output = run_cli_pty(
            [
                "--menu",
                "none",
                *(["--ssh"] if ssh_override else []),
                "-e",
                "AICAGE_ENTRYPOINT_CMD=bash",
                "--",
                "copilot",
                "-lc",
                (
                    "ssh -F /dev/null -p 2222 -o BatchMode=yes -o PasswordAuthentication=no "
                    "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                    "root@127.0.0.1 true"
                ),
            ],
            env=env,
            cwd=workspace,
        )
        assert exit_code == 0, output
    finally:
        project_cfg = store.load_project(workspace)
        project_cfg.agents["copilot"].docker_args = previous_docker_args
        store.save_project(workspace, project_cfg)
        subprocess.run(
            ["docker", "rm", "--force", container_name],
            check=False,
            capture_output=True,
        )


def _set_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    home_str = str(home)
    monkeypatch.setenv("HOME", home_str)
    if os.name == "nt":
        drive, tail = os.path.splitdrive(home_str)
        monkeypatch.setenv("USERPROFILE", home_str)
        if drive:
            monkeypatch.setenv("HOMEDRIVE", drive)
            monkeypatch.setenv("HOMEPATH", tail or "\\")


@contextmanager
def _ssh_agent(socket: Path) -> Iterator[dict[str, str]]:
    result = subprocess.run(
        ["ssh-agent", "-a", str(socket), "-s"],
        check=True,
        capture_output=True,
        text=True,
    )
    agent_env = dict(
        re.findall(r"^(SSH_[A-Z_]+)=([^;]+);", result.stdout, re.MULTILINE)
    )
    try:
        yield agent_env
    finally:
        subprocess.run(
            ["ssh-agent", "-k"],
            check=False,
            capture_output=True,
            env={**os.environ, **agent_env},
        )
