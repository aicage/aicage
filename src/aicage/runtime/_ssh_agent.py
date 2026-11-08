"""Host SSH agent forwarding."""

import glob
import os
import shlex
from pathlib import Path

from aicage.paths import HOST_SSH_DIR

_CONFIG_FILENAME = "config"
_KNOWN_HOST_FILENAMES = {"known_hosts", "known_hosts.old"}
_NON_KEY_FILENAMES = {
    _CONFIG_FILENAME,
    *_KNOWN_HOST_FILENAMES,
    "authorized_keys",
    "authorized_keys2",
}
_CONFIG_OPTION_VALUE_COUNT = 2


def _has_ssh_keys() -> bool:
    return bool(_resolve_ssh_key_files())


def _resolve_ssh_key_files() -> list[Path]:
    config_files = set(_resolve_ssh_config_files())
    paths = [
        path
        for path in _ssh_directory_files()
        if path not in config_files and _is_private_key_candidate(path)
    ]
    paths.extend(_configured_private_key_files())
    return list(dict.fromkeys(paths))


def _resolve_ssh_support_files() -> list[Path]:
    paths = [*_resolve_ssh_config_files()]
    known_hosts = HOST_SSH_DIR / "known_hosts"
    if known_hosts.is_file():
        paths.append(known_hosts)
    paths.extend(_public_key_files(_resolve_ssh_key_files()))
    return list(dict.fromkeys(paths))


def _resolve_ssh_config_files() -> list[Path]:
    config = HOST_SSH_DIR / _CONFIG_FILENAME
    if not config.is_file():
        return []
    return _config_files(config, set())


def _ssh_directory_files() -> list[Path]:
    if not HOST_SSH_DIR.is_dir():
        return []
    return [path for path in HOST_SSH_DIR.rglob("*") if path.is_file()]


def _is_private_key_candidate(path: Path) -> bool:
    return path.name not in _NON_KEY_FILENAMES and path.suffix != ".pub"


def _configured_private_key_files() -> list[Path]:
    paths: list[Path] = []
    for config in _resolve_ssh_config_files():
        for value in _config_values(config, "IdentityFile"):
            if "%" in value:
                continue
            path = Path(value).expanduser()
            if path.suffix == ".pub":
                path = path.with_suffix("")
            if path.is_file():
                paths.append(path)
    return paths


def _config_files(config: Path, seen: set[Path]) -> list[Path]:
    resolved = config.resolve()
    if resolved in seen:
        return []
    seen.add(resolved)
    paths = [config]
    for value in _config_values(config, "Include"):
        pattern = Path(value).expanduser()
        if not pattern.is_absolute():
            pattern = config.parent / pattern
        for match in glob.glob(str(pattern)):
            child = Path(match)
            if child.is_file():
                paths.extend(_config_files(child, seen))
    return paths


def _config_values(config: Path, option: str) -> list[str]:
    values: list[str] = []
    for line in config.read_text(encoding="utf-8").splitlines():
        tokens = shlex.split(line, comments=True, posix=os.name != "nt")
        if (
            len(tokens) >= _CONFIG_OPTION_VALUE_COUNT
            and tokens[0].lower() == option.lower()
        ):
            values.append(tokens[1])
    return values


def _public_key_files(private_keys: list[Path]) -> list[Path]:
    return [
        public_key
        for private_key in private_keys
        if (public_key := private_key.with_name(f"{private_key.name}.pub")).is_file()
    ]
