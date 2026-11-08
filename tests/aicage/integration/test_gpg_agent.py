import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from aicage.config.config_store import SettingsStore
from aicage.constants import CREDENTIAL_AGENT_IMAGE
from aicage.runtime.credential_agent import _resources
from aicage.runtime.credential_agent._env import _credential_agent_user
from aicage.runtime.credential_agent._resource_models import (
    _CredentialProtocol,
    _CredentialResource,
)

from ._helpers import (
    require_integration,
    run_cli_pty,
    setup_workspace,
    temporary_test_root,
)

pytestmark = pytest.mark.integration

_GPG_FINGERPRINT_FIELD = 9


def _gpg_resource() -> _CredentialResource:
    return _resources._resources([_CredentialProtocol.GPG])[0]


def test_gpg_agent_signs_through_direct_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name == "nt":
        pytest.skip("Windows always uses the GnuPG credential sidecar.")
    _assert_gpg_agent_signs(monkeypatch, use_sidecar=False)


def test_gpg_agent_signs_through_sidecar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_gpg_agent_signs(monkeypatch, use_sidecar=True)


def test_cached_protected_gpg_key_signs_through_direct_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name == "nt":
        pytest.skip("Windows always uses the GnuPG credential sidecar.")
    require_integration()
    initial_cwd = Path.cwd()
    temp_root = Path(__file__).resolve().parents[4] / ".aicage-test-tmp"
    temp_root.mkdir(exist_ok=True)
    with temporary_test_root(temp_root) as root:
        home = root / "home"
        try:
            home.mkdir()
            _set_home(monkeypatch, home)
            gpg_home = home / ".gnupg"
            fingerprint = _create_protected_gpg_fixture(gpg_home)
            _cache_protected_gpg_key(gpg_home, fingerprint, root / "host-cache")
            _assert_gpg_signs_without_pinentry(gpg_home, fingerprint, root / "host")
            workspace, env = setup_workspace(
                monkeypatch,
                root,
                "copilot",
                workspace_path=root / "workspace",
            )
            _enable_gnupg_mount(workspace)

            exit_code, output = run_cli_pty(
                [
                    "--menu",
                    "none",
                    "-e",
                    "AICAGE_ENTRYPOINT_CMD=bash",
                    "--",
                    "copilot",
                    "-lc",
                    (
                        "printf signed > signing-message "
                        f"&& gpg --batch --pinentry-mode error --local-user {shlex.quote(fingerprint)} "
                        "--detach-sign signing-message "
                        "&& gpg --verify signing-message.sig signing-message"
                    ),
                ],
                env=env,
                cwd=workspace,
            )

            assert exit_code == 0, output
        finally:
            monkeypatch.chdir(initial_cwd)


def test_gpg_sidecar_removes_deleted_host_keys(
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
            gpg_home = home / ".gnupg"
            workspace, env = setup_workspace(
                monkeypatch,
                tmp_path,
                "copilot",
                workspace_path=root / "workspace",
            )
            _enable_gnupg_mount(workspace)
            _create_gpg_sidecar_fixture(gpg_home)
            _force_gpg_sidecar(root, env)
            _run_credential_setup(workspace, env)
            _assert_gpg_sidecar_has_keygrips()
            shutil.rmtree(gpg_home / "private-keys-v1.d")
            _run_credential_setup(workspace, env)
            _assert_gpg_sidecar_has_no_keygrips()
        finally:
            monkeypatch.chdir(initial_cwd)


def test_protected_gpg_sidecar_key_does_not_block_noninteractive_run(
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
            gpg_home = home / ".gnupg"
            fingerprint = _create_gpg_sidecar_fixture(gpg_home, passphrase="secret")
            workspace, env = setup_workspace(
                monkeypatch,
                tmp_path,
                "copilot",
                workspace_path=root / "workspace",
            )
            _enable_gnupg_mount(workspace)
            _force_gpg_sidecar(root, env)

            _run_credential_setup(workspace, env)

            _assert_gpg_sidecar_key_is_unusable(fingerprint)
        finally:
            monkeypatch.chdir(initial_cwd)


def _assert_gpg_agent_signs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    use_sidecar: bool,
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
                root,
                "copilot",
                workspace_path=root / "workspace",
            )

            if use_sidecar:
                fingerprint = _create_gpg_sidecar_fixture(home / ".gnupg")
                _force_gpg_sidecar(root, env)
            else:
                fingerprint = _create_gpg_fixture(home / ".gnupg")
                _prime_host_gpg_agent(home / ".gnupg", fingerprint)
                _enable_gnupg_mount(workspace)

            # The sidecar run uses the CLI preference over the saved setting, which is off.
            credential_option = ["--gpg"] if use_sidecar else []
            exit_code, output = run_cli_pty(
                [
                    "--menu",
                    "none",
                    *credential_option,
                    "-e",
                    "AICAGE_ENTRYPOINT_CMD=bash",
                    "--",
                    "copilot",
                    "-lc",
                    (
                        "printf signed > signing-message "
                        f"&& gpg --batch --local-user {shlex.quote(fingerprint)} "
                        "--detach-sign signing-message "
                        "&& gpg --verify signing-message.sig signing-message "
                        '&& ! find "$GNUPGHOME/private-keys-v1.d" -type f '
                        "-print -quit 2>/dev/null | grep -q ."
                    ),
                ],
                env=env,
                cwd=workspace,
            )

            assert exit_code == 0, output
            if use_sidecar:
                subprocess.run(
                    ["docker", "stop", _gpg_resource().container_name],
                    check=True,
                    capture_output=True,
                )
                exit_code, output = run_cli_pty(
                    [
                        "--menu",
                        "none",
                        *credential_option,
                        "-e",
                        "AICAGE_ENTRYPOINT_CMD=bash",
                        "--",
                        "copilot",
                        "-lc",
                        (
                            "printf signed-after-restart > restart-message "
                            f"&& gpg --batch --local-user {shlex.quote(fingerprint)} "
                            "--detach-sign restart-message "
                            "&& gpg --verify restart-message.sig restart-message "
                            '&& ! find "$GNUPGHOME/private-keys-v1.d" -type f '
                            "-print -quit 2>/dev/null | grep -q ."
                        ),
                    ],
                    env=env,
                    cwd=workspace,
                )
                assert exit_code == 0, output
        finally:
            monkeypatch.chdir(initial_cwd)


def _enable_gnupg_mount(workspace: Path) -> None:
    store = SettingsStore()
    project_cfg = store.load_project(workspace)
    project_cfg.agents["copilot"].mounts.gnupg = True
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


def _set_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    home_str = str(home)
    monkeypatch.setenv("HOME", home_str)
    monkeypatch.setenv("GNUPGHOME", str(home / ".gnupg"))
    if os.name == "nt":
        drive, tail = os.path.splitdrive(home_str)
        monkeypatch.setenv("USERPROFILE", home_str)
        if drive:
            monkeypatch.setenv("HOMEDRIVE", drive)
            monkeypatch.setenv("HOMEPATH", tail or "\\")


def _force_gpg_sidecar(root: Path, env: dict[str, str]) -> None:
    if os.name == "nt":
        return
    gpgconf = shutil.which("gpgconf")
    if gpgconf is None:
        raise AssertionError("gpgconf is required to force the GnuPG sidecar.")
    bin_dir = root / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "gpgconf"
    shim.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                'if [ "$1" = "--list-dirs" ] && [ "$2" = "agent-socket" ]; then',
                "  exit 0",
                "fi",
                f'exec {shlex.quote(gpgconf)} "$@"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    shim.chmod(0o755)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"


def _create_gpg_fixture(gpg_home: Path) -> str:
    gpg_home.mkdir(mode=0o700)
    _create_gpg_fixture_on_host(gpg_home)
    result = _list_gpg_secret_keys_on_host(gpg_home)
    return _gpg_key_fingerprint(result.stdout)


def _create_gpg_fixture_on_host(gpg_home: Path) -> None:
    result = subprocess.run(
        [
            *_gpg_command(),
            "--batch",
            "--passphrase",
            "",
            "--quick-generate-key",
            "Aicage Integration <integration@example.com>",
            "ed25519",
            "sign",
            "never",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=_gpg_environment(gpg_home),
    )
    if result.returncode != 0:
        raise AssertionError(
            f"GnuPG key generation failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def _create_protected_gpg_fixture(gpg_home: Path) -> str:
    gpg_home.mkdir(mode=0o700)
    result = subprocess.run(
        [
            *_gpg_command(),
            "--batch",
            "--pinentry-mode",
            "loopback",
            "--passphrase",
            "secret",
            "--quick-generate-key",
            "Aicage Integration <integration@example.com>",
            "ed25519",
            "sign",
            "never",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=_gpg_environment(gpg_home),
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Protected GnuPG key generation failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    fingerprints, _ = _gpg_secret_key_state(gpg_home)
    return fingerprints[0]


def _cache_protected_gpg_key(gpg_home: Path, fingerprint: str, directory: Path) -> None:
    message = directory.with_suffix(".message")
    signature = directory.with_suffix(".sig")
    message.write_text("aicage cache integration\n", encoding="utf-8")
    result = subprocess.run(
        [
            *_gpg_command(),
            "--homedir",
            str(gpg_home),
            "--batch",
            "--pinentry-mode",
            "loopback",
            "--passphrase",
            "secret",
            "--local-user",
            fingerprint,
            "--detach-sign",
            "--output",
            str(signature),
            str(message),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=_gpg_environment(gpg_home),
    )
    assert result.returncode == 0, result.stderr


def _assert_gpg_signs_without_pinentry(
    gpg_home: Path, fingerprint: str, directory: Path
) -> None:
    message = directory.with_suffix(".message")
    signature = directory.with_suffix(".sig")
    message.write_text("aicage integration\n", encoding="utf-8")
    result = subprocess.run(
        [
            *_gpg_command(),
            "--homedir",
            str(gpg_home),
            "--batch",
            "--pinentry-mode",
            "error",
            "--local-user",
            fingerprint,
            "--detach-sign",
            "--output",
            str(signature),
            str(message),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=_gpg_environment(gpg_home),
    )
    assert result.returncode == 0, result.stderr


def _list_gpg_secret_keys_on_host(gpg_home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            *_gpg_command(),
            "--batch",
            "--with-colons",
            "--with-keygrip",
            "--list-secret-keys",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=_gpg_environment(gpg_home),
    )


def _gpg_secret_key_state(gpg_home: Path) -> tuple[list[str], set[str]]:
    result = _list_gpg_secret_keys_on_host(gpg_home)
    secret_key_present = any(
        line.startswith("sec:") for line in result.stdout.splitlines()
    )
    fingerprints = [_gpg_key_fingerprint(result.stdout)] if secret_key_present else []
    keygrips = {
        fields[_GPG_FINGERPRINT_FIELD]
        for line in result.stdout.splitlines()
        if (fields := line.split(":"))
        and fields[0] == "grp"
        and len(fields) > _GPG_FINGERPRINT_FIELD
    }
    return fingerprints, keygrips


def _gpg_key_fingerprint(stdout: str) -> str:
    for line in stdout.splitlines():
        fields = line.split(":")
        if fields[0] == "fpr":
            return fields[9]
    raise AssertionError("Generated GnuPG key has no fingerprint.")


def _create_gpg_sidecar_fixture(gpg_home: Path, *, passphrase: str = "") -> str:
    gpg_home.mkdir(mode=0o700)
    mount = f"type=bind,src={gpg_home},dst=/credential/gnupg"
    user = _credential_agent_user()
    generate_key = (
        "gpg --batch --passphrase '' "
        "--quick-generate-key 'Aicage Integration <integration@example.com>' "
        "ed25519 sign never"
        if not passphrase
        else (
            f"printf '%s\\n' {shlex.quote(passphrase)} | "
            "gpg --batch --pinentry-mode loopback --passphrase-fd 0 "
            "--quick-generate-key 'Aicage Integration <integration@example.com>' "
            "ed25519 sign never"
        )
    )
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--user",
            user,
            "--entrypoint",
            "/bin/sh",
            "-e",
            "GNUPGHOME=/credential/gnupg",
            "--mount",
            mount,
            CREDENTIAL_AGENT_IMAGE,
            "-c",
            'chmod 700 "$GNUPGHOME" && '
            f"{generate_key} && gpg --batch --with-colons --list-secret-keys",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"GnuPG sidecar fixture generation failed:\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return _gpg_key_fingerprint(result.stdout)


def _assert_gpg_sidecar_has_keygrips() -> None:
    result = subprocess.run(
        [
            "docker",
            "exec",
            _gpg_resource().container_name,
            "credential-agent",
            "gpg",
            "keygrips",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip()


def _assert_gpg_sidecar_has_no_keygrips() -> None:
    result = subprocess.run(
        [
            "docker",
            "exec",
            _gpg_resource().container_name,
            "credential-agent",
            "gpg",
            "keygrips",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert not result.stdout.strip()


def _assert_gpg_sidecar_key_is_unusable(fingerprint: str) -> None:
    result = subprocess.run(
        [
            "docker",
            "exec",
            _gpg_resource().container_name,
            "credential-agent",
            "gpg",
            "usable",
            fingerprint,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "unusable"


def _assert_gpg_sidecar_client_signs(
    root: Path, gpg_home: Path, fingerprint: str
) -> None:
    client_home = root / "client-gnupg"
    shutil.rmtree(client_home, ignore_errors=True)
    client_home.mkdir(mode=0o700)
    for filename in ("pubring.kbx", "trustdb.gpg"):
        source = gpg_home / filename
        if source.is_file():
            shutil.copy2(source, client_home / filename)
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--user",
            _credential_agent_user(),
            "--entrypoint",
            "/bin/sh",
            "--mount",
            f"type=volume,src={_gpg_resource().volume_name},"
            "dst=/run/credential-agent,readonly",
            "--mount",
            f"type=bind,src={client_home},dst=/client-gnupg",
            CREDENTIAL_AGENT_IMAGE,
            "-c",
            "ln -s /run/credential-agent/S.gpg-agent /client-gnupg/S.gpg-agent "
            "&& printf signed > /client-gnupg/message "
            f"&& GNUPGHOME=/client-gnupg gpg --batch --local-user {fingerprint} "
            "--detach-sign /client-gnupg/message "
            "&& GNUPGHOME=/client-gnupg gpg --verify /client-gnupg/message.sig "
            "/client-gnupg/message",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert (
        result.returncode == 0
    ), f"GnuPG sidecar client failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert not any((client_home / "private-keys-v1.d").glob("*"))


def _prime_host_gpg_agent(gpg_home: Path, fingerprint: str) -> None:
    env = _gpg_environment(gpg_home)
    result = subprocess.run(
        [*_gpg_command(), "--batch", "--with-colons", "--list-secret-keys"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    if fingerprint not in result.stdout:
        raise AssertionError("Host GnuPG did not find the generated secret key.")


def _gpg_command() -> list[str]:
    if os.name != "nt":
        return ["gpg"]
    gpg = Path(os.environ["ProgramFiles"]) / "Git" / "usr" / "bin" / "gpg.exe"
    if not gpg.is_file():
        raise AssertionError(f"Git for Windows did not provide gpg.exe at {gpg}.")
    return [str(gpg)]


def _gpg_environment(gpg_home: Path) -> dict[str, str]:
    env = {**os.environ, "GNUPGHOME": str(gpg_home)}
    if os.name == "nt":
        result = subprocess.run(
            ["cygpath", "--unix", str(gpg_home)],
            check=True,
            capture_output=True,
            text=True,
        )
        env["GNUPGHOME"] = result.stdout.strip()
    return env
