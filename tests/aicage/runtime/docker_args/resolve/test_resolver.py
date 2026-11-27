import tempfile
from pathlib import Path, PurePosixPath
from unittest import TestCase, mock

from aicage.cli_types import ParsedArgs
from aicage.config.agent.models import AgentMetadata
from aicage.config.base.models import BaseMetadata
from aicage.config.context import ConfigContext
from aicage.config.project_config import AgentConfig, _ProjectConfig
from aicage.paths import container_project_path
from aicage.runtime.docker_args.resolve import resolver
from aicage.runtime.docker_args.resolve._mounts import map_mount_requests
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest, ResolvedArgs
from aicage.runtime.env_vars import _AICAGE_WORKSPACE
from aicage.runtime.run_args import BindMountSpec, EnvVar

_MODULE = "aicage.runtime.docker_args.resolve.resolver"


class ResolverTests(TestCase):
    def test_validate_home_mount_safety_allows_windows_named_pipe(self) -> None:
        pipe_path = Path(r"\\.\pipe\docker_engine")
        with mock.patch(
            f"{_MODULE}.get_active_docker_host",
            return_value=mock.Mock(named_pipe_path=pipe_path),
        ):
            resolver._validate_home_mount_safety(
                [
                    BindMountSpec(
                        host_path=pipe_path,
                        container_path=PurePosixPath("/var/run/docker.sock"),
                    )
                ],
                Path("/test-tmp/home"),
            )

    def test_resolve_docker_args_aggregates_mounts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir).resolve()
            home_path = temp_path / "home"
            project_path = temp_path / "project"
            home_path.mkdir()
            project_path.mkdir()
            git_config = home_path / ".gitconfig"
            docker_sock = temp_path / "docker.sock"

            project_cfg, context = self._build_context(project_path)
            parsed = self._build_parsed()

            with (
                mock.patch(
                    f"{_MODULE}.project.resolve",
                    return_value=ResolvedArgs(
                        mounts=[MountRequest(host_path=project_path)]
                    ),
                ),
                mock.patch(
                    f"{_MODULE}.agent_config.resolve", return_value=ResolvedArgs()
                ),
                mock.patch(
                    f"{_MODULE}.git_config.resolve",
                    return_value=ResolvedArgs(
                        mounts=[MountRequest(host_path=git_config)]
                    ),
                ) as git_mock,
                mock.patch(f"{_MODULE}.git_root.resolve", return_value=ResolvedArgs()),
                mock.patch(
                    f"{_MODULE}.docker_socket.resolve",
                    return_value=ResolvedArgs(
                        mounts=[MountRequest(host_path=docker_sock)],
                        env=[EnvVar(name="DOCKER_HOST", value="tcp://host:2375")],
                    ),
                ) as docker_mock,
                mock.patch(f"{_MODULE}.shares.resolve", return_value=ResolvedArgs()),
                mock.patch(f"{_MODULE}.Path.home", return_value=home_path),
            ):
                mounts, env = resolver.resolve_docker_args(context, "codex", parsed)

        self.assertEqual(
            [
                BindMountSpec(
                    host_path=docker_sock,
                    container_path=container_project_path(docker_sock),
                ),
                BindMountSpec(
                    host_path=project_path,
                    container_path=container_project_path(project_path),
                ),
                BindMountSpec(
                    host_path=git_config,
                    container_path=container_project_path(git_config),
                ),
            ],
            mounts,
        )
        self.assertEqual(
            [
                ("DOCKER_HOST", "tcp://host:2375"),
                (_AICAGE_WORKSPACE, container_project_path(project_path).as_posix()),
            ],
            [(item.name, item.value) for item in env],
        )
        git_mock.assert_called_once_with(context, "codex", parsed)
        docker_mock.assert_called_once_with(context, "codex", parsed)

    def test_resolve_docker_args_inserts_agent_config(self) -> None:
        project_cfg = _ProjectConfig(path="/test-tmp/project", agents={})
        context = ConfigContext(
            store=mock.Mock(),
            project_cfg=project_cfg,
            agents=self._get_agents(),
            bases=self._get_bases(),
            extensions={},
        )

        with (
            mock.patch(f"{_MODULE}.project.resolve", return_value=ResolvedArgs()),
            mock.patch(f"{_MODULE}.agent_config.resolve", return_value=ResolvedArgs()),
            mock.patch(f"{_MODULE}.git_config.resolve", return_value=ResolvedArgs()),
            mock.patch(f"{_MODULE}.git_root.resolve", return_value=ResolvedArgs()),
            mock.patch(f"{_MODULE}.docker_socket.resolve", return_value=ResolvedArgs()),
            mock.patch(f"{_MODULE}.shares.resolve", return_value=ResolvedArgs()),
            mock.patch(f"{_MODULE}.Path.home", return_value=Path("/test-tmp/home")),
        ):
            resolver.resolve_docker_args(context, "codex", None)

        self.assertIsInstance(project_cfg.agents["codex"], AgentConfig)

    def test_resolve_docker_args_uses_host_path_for_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_path = Path(temp_dir).resolve() / "home"
            project_path = home_path / "project"
            home_path.mkdir()
            project_path.mkdir()

            _, context = self._build_context(project_path)
            parsed = self._build_parsed()

            with (
                mock.patch(
                    f"{_MODULE}.project.resolve",
                    return_value=ResolvedArgs(
                        mounts=[MountRequest(host_path=project_path)]
                    ),
                ),
                mock.patch(
                    f"{_MODULE}.agent_config.resolve", return_value=ResolvedArgs()
                ),
                mock.patch(
                    f"{_MODULE}.git_config.resolve", return_value=ResolvedArgs()
                ),
                mock.patch(f"{_MODULE}.git_root.resolve", return_value=ResolvedArgs()),
                mock.patch(
                    f"{_MODULE}.docker_socket.resolve", return_value=ResolvedArgs()
                ),
                mock.patch(f"{_MODULE}.shares.resolve", return_value=ResolvedArgs()),
                mock.patch(f"{_MODULE}.Path.home", return_value=home_path),
            ):
                mounts, env = resolver.resolve_docker_args(context, "codex", parsed)

        self.assertEqual(
            [
                BindMountSpec(
                    host_path=project_path,
                    container_path=container_project_path(project_path),
                )
            ],
            mounts,
        )
        self.assertEqual(
            [
                (_AICAGE_WORKSPACE, container_project_path(project_path).as_posix()),
            ],
            [(item.name, item.value) for item in env],
        )

    def test_map_mount_requests_deduplicates_nested_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root_path = Path(temp_dir).resolve()
            parent_path = root_path / "parent"
            child_path = parent_path / "child"
            parent_path.mkdir()
            child_path.mkdir()

            mounts = map_mount_requests(
                [
                    MountRequest(host_path=child_path, read_only=False),
                    MountRequest(host_path=parent_path, read_only=False),
                ]
            )

        self.assertEqual(
            [
                BindMountSpec(
                    host_path=parent_path,
                    container_path=container_project_path(parent_path),
                    read_only=False,
                )
            ],
            mounts,
        )

    @staticmethod
    def _get_bases() -> dict[str, BaseMetadata]:
        return {
            "ubuntu": BaseMetadata(
                from_image="ubuntu:latest",
                base_image_distro="Ubuntu",
                base_image_description="Default",
                architectures=["amd64", "arm64"],
                build_local=False,
                local_definition_dir=Path("/test-tmp/base"),
            )
        }

    @staticmethod
    def _get_agents() -> dict[str, AgentMetadata]:
        return {
            "codex": AgentMetadata(
                agent_path_files=[],
                agent_path_directories=["~/.codex"],
                agent_full_name="Codex CLI",
                agent_homepage="https://example.com",
                build_local=False,
                valid_bases={"ubuntu": "ghcr.io/aicage/aicage:codex-ubuntu"},
                local_definition_dir=Path("/test-tmp/agent"),
            )
        }

    def _build_context(
        self, project_path: Path
    ) -> tuple[_ProjectConfig, ConfigContext]:
        project_cfg = _ProjectConfig(
            path=str(project_path), agents={"codex": AgentConfig()}
        )
        context = ConfigContext(
            store=mock.Mock(),
            project_cfg=project_cfg,
            agents=self._get_agents(),
            bases=self._get_bases(),
            extensions={},
        )
        return project_cfg, context

    @staticmethod
    def _build_parsed() -> ParsedArgs:
        return ParsedArgs(False, "", "codex", [], False, [])
