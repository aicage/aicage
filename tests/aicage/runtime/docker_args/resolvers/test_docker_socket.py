from pathlib import Path, PurePosixPath
from unittest import TestCase, mock

from aicage.cli_types import ParsedArgs
from aicage.config.context import ConfigContext
from aicage.config.project_config import AgentConfig, _AgentMounts, _ProjectConfig
from aicage.paths import HOST_DOCKER_SOCKET_PATH
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest
from aicage.runtime.docker_args.resolvers.docker_socket import resolve
from aicage.runtime.env_vars import DOCKER_HOST

_MODULE = "aicage.runtime.docker_args.resolvers.docker_socket"


class DockerSocketMountTests(TestCase):
    def test_resolve_docker_socket_mount_uses_cli_socket_without_persisting(
        self,
    ) -> None:
        agent_cfg = AgentConfig()
        context = _build_context(agent_cfg)
        parsed = _build_parsed(docker_socket=True)
        with (
            mock.patch(f"{_MODULE}.os.name", "posix"),
            mock.patch(
                f"{_MODULE}.get_active_docker_host",
                return_value=mock.Mock(
                    host="unix:///run/docker.sock",
                    socket_path=HOST_DOCKER_SOCKET_PATH,
                    named_pipe_path=None,
                ),
            ),
        ):
            resolved = resolve(context, "codex", parsed)

        self.assertIsNone(agent_cfg.mounts.docker)
        self.assertEqual(1, len(resolved.mounts))
        self.assertEqual("/run/docker.sock", resolved.mounts[0].host_path.as_posix())
        self.assertEqual([], resolved.env)

    def test_resolve_docker_socket_mount_uses_persisted_socket(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(docker=True))
        context = _build_context(agent_cfg)
        with (
            mock.patch(f"{_MODULE}.os.name", "posix"),
            mock.patch(
                f"{_MODULE}.get_active_docker_host",
                return_value=mock.Mock(
                    host="unix:///run/docker.sock",
                    socket_path=HOST_DOCKER_SOCKET_PATH,
                    named_pipe_path=None,
                ),
            ),
        ):
            resolved = resolve(context, "codex", _build_parsed())

        self.assertEqual(1, len(resolved.mounts))
        self.assertEqual([], resolved.env)

    def test_resolve_docker_socket_mount_disabled(self) -> None:
        agent_cfg = AgentConfig()
        context = _build_context(agent_cfg)
        resolved = resolve(context, "codex", _build_parsed())

        self.assertEqual([], resolved.mounts)
        self.assertEqual([], resolved.env)

    def test_resolve_docker_socket_mount_windows_uses_engine_socket(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(docker=True))
        context = _build_context(agent_cfg)
        with mock.patch(f"{_MODULE}.os.name", "nt"):
            resolved = resolve(context, "codex", _build_parsed())

        self.assertEqual(
            [
                MountRequest(
                    host_path=HOST_DOCKER_SOCKET_PATH,
                    container_path=PurePosixPath("/var/run/docker.sock"),
                )
            ],
            resolved.mounts,
        )
        self.assertEqual(
            [(DOCKER_HOST, "unix:///var/run/docker.sock")],
            [(item.name, item.value) for item in resolved.env],
        )

    def test_resolve_docker_socket_mount_windows_ignores_named_pipe_context(
        self,
    ) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(docker=True))
        context = _build_context(agent_cfg)
        named_pipe = Path(r"\\.\pipe\docker_engine")
        with (
            mock.patch(f"{_MODULE}.os.name", "nt"),
            mock.patch(
                f"{_MODULE}.get_active_docker_host",
                return_value=mock.Mock(
                    named_pipe_path=named_pipe,
                    socket_path=None,
                    host="npipe:////./pipe/docker_engine",
                ),
            ),
        ):
            resolved = resolve(context, "codex", _build_parsed())

        self.assertEqual(
            [
                MountRequest(
                    host_path=HOST_DOCKER_SOCKET_PATH,
                    container_path=PurePosixPath("/var/run/docker.sock"),
                )
            ],
            resolved.mounts,
        )
        self.assertEqual(
            [(DOCKER_HOST, "unix:///var/run/docker.sock")],
            [(item.name, item.value) for item in resolved.env],
        )


def _build_context(agent_cfg: AgentConfig) -> ConfigContext:
    project_cfg = _ProjectConfig(path="/test-tmp/project", agents={"codex": agent_cfg})
    return ConfigContext(
        store=mock.Mock(),
        project_cfg=project_cfg,
        agents={},
        bases={},
        extensions={},
    )


def _build_parsed(docker_socket: bool = False) -> ParsedArgs:
    return ParsedArgs(False, "", "codex", [], docker_socket, [], "none")
