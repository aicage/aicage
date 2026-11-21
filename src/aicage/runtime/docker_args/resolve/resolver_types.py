from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Protocol

from aicage.cli_types import ParsedArgs
from aicage.config.context import ConfigContext
from aicage.runtime.run_args import EnvVar


@dataclass(frozen=True)
class MountRequest:
    host_path: Path
    read_only: bool = False
    container_path: PurePosixPath | None = None


@dataclass(frozen=True)
class ResolvedArgs:
    mounts: list[MountRequest] = field(default_factory=list)
    env: list[EnvVar] = field(default_factory=list)


class _Resolver(Protocol):
    def __call__(
        self,
        context: ConfigContext,
        agent: str,
        parsed: ParsedArgs | None,
    ) -> ResolvedArgs: ...
