"""Host GnuPG discovery."""

import subprocess  # nosec B404 -- GnuPG discovery uses fixed local commands.
from pathlib import Path

from aicage.paths import HOST_GNUPG_DIR

_GPG_FINGERPRINT_FIELD = 9


def resolve_gpg_home() -> Path | None:
    stdout = _capture_stdout(["gpgconf", "--list-dirs", "homedir"])
    if stdout:
        path = stdout.strip()
        if path:
            home = Path(path).expanduser()
            if home.exists():
                return home
    return HOST_GNUPG_DIR if HOST_GNUPG_DIR.exists() else None


def resolve_gpg_agent_socket() -> Path | None:
    stdout = _capture_stdout(["gpgconf", "--list-dirs", "agent-socket"])
    path = stdout.strip() if stdout else ""
    return Path(path).expanduser() if path else None


def resolve_gpg_public_files(gpg_home: Path) -> list[Path]:
    paths = [
        path
        for path in (
            gpg_home / "common.conf",
            gpg_home / "gpg.conf",
            gpg_home / "pubring.kbx",
            gpg_home / "pubring.gpg",
            gpg_home / "public-keys.d" / "pubring.db",
            gpg_home / "trustdb.gpg",
            gpg_home / "tofu.db",
        )
        if path.is_file()
    ]
    config = gpg_home / "gpg.conf"
    if config.is_file():
        paths.extend(_configured_gpg_public_files(config, gpg_home))
    return list(dict.fromkeys(paths))


def has_gpg_keys() -> bool:
    gpg_home = resolve_gpg_home()
    if gpg_home is None:
        return False
    private_keys = gpg_home / "private-keys-v1.d"
    return private_keys.is_dir() and any(private_keys.iterdir())


def resolve_gpg_secret_key_state() -> tuple[list[str], set[str]]:
    output = _capture_stdout(
        ["gpg", "--batch", "--with-colons", "--with-keygrip", "--list-secret-keys"]
    )
    if output is None:
        return [], set()
    fingerprints: list[str] = []
    keygrips: set[str] = set()
    pending = False
    for line in output.splitlines():
        fields = line.split(":")
        if fields[0] == "sec":
            pending = len(fields) > 1 and fields[1] not in {"d", "e", "i", "r"}
        elif fields[0] == "fpr" and pending and len(fields) > _GPG_FINGERPRINT_FIELD:
            fingerprints.append(fields[_GPG_FINGERPRINT_FIELD])
            pending = False
        elif fields[0] == "ssb":
            pending = False
        elif fields[0] == "grp" and len(fields) > _GPG_FINGERPRINT_FIELD:
            keygrips.add(fields[_GPG_FINGERPRINT_FIELD])
    return fingerprints, keygrips


def _capture_stdout(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command, check=False, capture_output=True, text=True
        )  # nosec B603
    except FileNotFoundError:
        return None
    return result.stdout if result.returncode == 0 else None


def _resolve_gpg_secret_key_fingerprints() -> list[str]:
    return resolve_gpg_secret_key_state()[0]


def _configured_gpg_public_files(config: Path, home: Path) -> list[Path]:
    paths: list[Path] = []
    for line in config.read_text(encoding="utf-8").splitlines():
        value = _gpg_config_public_file_value(line)
        if value is not None:
            path = Path(value).expanduser()
            paths.append(path if path.is_absolute() else home / path)
    return [path for path in paths if path.is_file()]


def _gpg_config_public_file_value(line: str) -> str | None:
    value = line.strip()
    if not value or value.startswith("#"):
        return None
    option, separator, path = value.partition(" ")
    if option not in {"keyring", "trustdb-name"} or not separator:
        return None
    return path.strip() or None
