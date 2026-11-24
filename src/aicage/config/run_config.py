from dataclasses import dataclass
from pathlib import Path

from aicage.config.context import ConfigContext
from aicage.registry.image_selection.models import ImageSelection
from aicage.runtime.run_args import BindMountSpec, EnvVar


@dataclass(frozen=True)
class RunConfig:
    project_path: Path
    agent: str
    context: ConfigContext
    selection: ImageSelection
    project_docker_args: str
    mounts: list[BindMountSpec]
    env: list[EnvVar]
