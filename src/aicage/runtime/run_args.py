from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath


@dataclass
class MountSpec:
    pass


@dataclass
class BindMountSpec(MountSpec):
    host_path: Path
    container_path: PurePosixPath
    read_only: bool = False


@dataclass
class VolumeMountSpec(MountSpec):
    volume_name: str
    container_path: PurePosixPath
    read_only: bool = False


@dataclass(frozen=True)
class EnvVar:
    name: str
    value: str


@dataclass
class DockerRunArgs:
    image_ref: str
    merged_docker_args: str
    agent_args: list[str]
    env: list[EnvVar] = field(default_factory=list)
    mounts: list[MountSpec] = field(default_factory=list)


def _merge_docker_args(*args: str) -> str:
    return " ".join(part for part in args if part).strip()
