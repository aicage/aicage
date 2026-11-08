import os
from os.path import expanduser
from pathlib import Path, PurePosixPath, PureWindowsPath

# AICAGE PATHS (for Python program on host)

_AGENT_DEFINITION_FILENAME: str = "agent.yml"
EXTENDED_IMAGE_DEFINITION_FILENAME: str = "image-extended.yml"

_CONFIG_BASE_DIR: Path = Path(expanduser("~/.aicage"))
_CONFIG_DIR: Path = _CONFIG_BASE_DIR / "config"
PROJECTS_DIR: Path = _CONFIG_BASE_DIR / "projects"
GLOBAL_CONFIG_PATH: Path = _CONFIG_DIR / "global.yml"
TREES_DIR: Path = _CONFIG_DIR / "trees"

BASE_IMAGE_BUILD_STATE_DIR: Path = _CONFIG_BASE_DIR / "state/base-image/build"
IMAGE_BUILD_STATE_DIR: Path = _CONFIG_BASE_DIR / "state/image/build"
AGENT_VERSION_CHECK_STATE_DIR: Path = (
    _CONFIG_BASE_DIR / "state/agent/version-check/state"
)
IMAGE_EXTENDED_STATE_DIR: Path = _CONFIG_BASE_DIR / "state/image-extended/state"
IMAGE_EXTENDED_BUILD_STATE_DIR: Path = _CONFIG_BASE_DIR / "state/image-extended/build"
CREDENTIAL_AGENT_LOCK_PATH: Path = _CONFIG_BASE_DIR / "state/credential-agent.lock"

_LOG_DIR: Path = _CONFIG_BASE_DIR / "logs"
GLOBAL_LOG_PATH: Path = _LOG_DIR / "aicage.log"
IMAGE_PULL_LOG_DIR: Path = _LOG_DIR / "image/pull"
BASE_IMAGE_BUILD_LOG_DIR: Path = _LOG_DIR / "base-image/build"
IMAGE_BUILD_LOG_DIR: Path = _LOG_DIR / "image/build"
IMAGE_EXTENDED_BUILD_LOG_DIR: Path = _LOG_DIR / "image-extended/build"

# Only user-generated custom files outside ~/.aicage.
_CUSTOM_ROOT_DIR: Path = Path(expanduser("~/.aicage-custom"))

CUSTOM_BASES_DIR: Path = _CUSTOM_ROOT_DIR / "base-images"
CUSTOM_BASE_DEFINITION_FILES: tuple[str, str] = (
    "base.yaml",
    "base.yml",
)

CUSTOM_AGENTS_DIR: Path = _CUSTOM_ROOT_DIR / "agents"
CUSTOM_AGENT_DEFINITION_FILES: tuple[str, str] = (
    _AGENT_DEFINITION_FILENAME,
    "agent.yaml",
)

CUSTOM_EXTENSIONS_DIR: Path = _CUSTOM_ROOT_DIR / "extensions"
CUSTOM_EXTENSION_DEFINITION_FILES: tuple[str, str] = (
    "extension.yaml",
    "extension.yml",
)

# OTHER HOST PATHS (for mounts to container)

HOST_SSH_DIR: Path = Path.home() / ".ssh"
HOST_GNUPG_DIR: Path = Path.home() / ".gnupg"
HOST_DOCKER_SOCKET_PATH: Path = Path("/run/docker.sock")

# CONTAINER PATHS (for mounts to container)

_WSL_MOUNT_ROOT: PurePosixPath = PurePosixPath("/mnt")


def container_project_path(host_path: Path) -> PurePosixPath:
    if os.name != "nt":
        return PurePosixPath(host_path.as_posix())
    win_path = PureWindowsPath(host_path)
    drive = win_path.drive
    if drive.startswith("\\\\?\\"):
        drive = drive[4:]
    drive_letter = drive.rstrip(":").lower()
    if not drive_letter:
        return PurePosixPath(host_path.as_posix())
    parts = [part for part in win_path.parts if part != win_path.anchor]
    return _WSL_MOUNT_ROOT / drive_letter / PurePosixPath(*parts)
