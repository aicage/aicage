import os
from contextlib import nullcontext
from pathlib import Path
from unittest import TestCase, mock

from aicage.cli_types import ParsedArgs
from aicage.config.agent.models import AgentMetadata
from aicage.config.base.models import BaseMetadata
from aicage.config.context import ConfigContext
from aicage.config.project_config import AgentConfig, _AgentMounts, _ProjectConfig
from aicage.config.runtime_config import RunConfig
from aicage.registry.image_selection.models import ImageSelection
from aicage.runtime.run_args import DockerRunArgs, EnvVar
from aicage.runtime.run_plan import (
    _build_run_args,
    _host_timezone_env,
    prepare_run_args,
)


class RunPlanTests(TestCase):
    def test_build_run_args_merges_docker_args(self) -> None:
        project_path = Path("/test-tmp/project")
        config = RunConfig(
            project_path=project_path,
            agent="codex",
            context=ConfigContext(
                store=mock.Mock(),
                project_cfg=_ProjectConfig(path=str(project_path), agents={}),
                agents=self._get_agents(),
                bases=self._get_bases(),
                extensions={},
            ),
            selection=ImageSelection(
                image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
                base="ubuntu",
                extensions=[],
                agent_image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
            ),
            project_docker_args="--project",
            mounts=[],
            env=[],
        )
        parsed = ParsedArgs(False, "--cli", "codex", ["--flag"], False, [])
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch(
                "aicage.runtime.run_plan.resolve_host_timezone", return_value=None
            ),
        ):
            run_args = _build_run_args(config, parsed)

        self.assertEqual("--project --cli", run_args.merged_docker_args)
        self.assertEqual(["--flag"], run_args.agent_args)

    def test_build_run_args_uses_mounts_from_config(self) -> None:
        project_path = Path("/test-tmp/project")
        mount = mock.Mock()
        config = RunConfig(
            project_path=project_path,
            agent="codex",
            context=ConfigContext(
                store=mock.Mock(),
                project_cfg=_ProjectConfig(path=str(project_path), agents={}),
                agents=self._get_agents(),
                bases=self._get_bases(),
                extensions={},
            ),
            selection=ImageSelection(
                image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
                base="ubuntu",
                extensions=[],
                agent_image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
            ),
            project_docker_args="",
            mounts=[mount],
            env=[],
        )
        parsed = ParsedArgs(False, "", "codex", [], False, [])
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch(
                "aicage.runtime.run_plan.resolve_host_timezone", return_value=None
            ),
        ):
            run_args = _build_run_args(config, parsed)

        self.assertEqual([mount], run_args.mounts)

    def test_build_run_args_uses_env_from_config(self) -> None:
        project_path = Path("/test-tmp/project")
        mount = mock.Mock()
        env = [EnvVar(name="EXTRA", value="1")]
        config = RunConfig(
            project_path=project_path,
            agent="codex",
            context=ConfigContext(
                store=mock.Mock(),
                project_cfg=_ProjectConfig(path=str(project_path), agents={}),
                agents=self._get_agents(),
                bases=self._get_bases(),
                extensions={},
            ),
            selection=ImageSelection(
                image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
                base="ubuntu",
                extensions=[],
                agent_image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
            ),
            project_docker_args="",
            mounts=[mount],
            env=env,
        )
        parsed = ParsedArgs(False, "", "codex", [], False, [])
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch(
                "aicage.runtime.run_plan.resolve_host_timezone", return_value=None
            ),
        ):
            run_args = _build_run_args(config, parsed)

        self.assertEqual([mount], run_args.mounts)
        self.assertEqual(env, run_args.env)

    def test_build_run_args_appends_proxy_env_from_host(self) -> None:
        project_path = Path("/test-tmp/project")
        config = RunConfig(
            project_path=project_path,
            agent="codex",
            context=ConfigContext(
                store=mock.Mock(),
                project_cfg=_ProjectConfig(path=str(project_path), agents={}),
                agents=self._get_agents(),
                bases=self._get_bases(),
                extensions={},
            ),
            selection=ImageSelection(
                image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
                base="ubuntu",
                extensions=[],
                agent_image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
            ),
            project_docker_args="",
            mounts=[],
            env=[EnvVar(name="EXTRA", value="1")],
        )
        parsed = ParsedArgs(False, "", "codex", [], False, [])
        with (
            mock.patch(
                "aicage._proxy.os.environ",
                {
                    "HTTP_PROXY": "http://proxy-http:8080",
                    "HTTPS_PROXY": "http://proxy-https:8080",
                    "http_proxy": "http://ignored:8080",
                },
            ),
            mock.patch(
                "aicage.runtime.run_plan.resolve_host_timezone", return_value=None
            ),
        ):
            run_args = _build_run_args(config, parsed)

        self.assertEqual(
            [
                EnvVar(name="EXTRA", value="1"),
                EnvVar(name="HTTP_PROXY", value="http://proxy-http:8080"),
                EnvVar(name="HTTPS_PROXY", value="http://proxy-https:8080"),
            ],
            run_args.env,
        )

    def test_build_run_args_appends_timezone_env(self) -> None:
        project_path = Path("/test-tmp/project")
        config = RunConfig(
            project_path=project_path,
            agent="codex",
            context=ConfigContext(
                store=mock.Mock(),
                project_cfg=_ProjectConfig(path=str(project_path), agents={}),
                agents=self._get_agents(),
                bases=self._get_bases(),
                extensions={},
            ),
            selection=ImageSelection(
                image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
                base="ubuntu",
                extensions=[],
                agent_image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
            ),
            project_docker_args="",
            mounts=[],
            env=[],
        )
        parsed = ParsedArgs(False, "", "codex", [], False, [])
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch(
                "aicage.runtime.run_plan.resolve_host_timezone",
                return_value="Europe/Zurich",
            ),
        ):
            run_args = _build_run_args(config, parsed)

        self.assertEqual([EnvVar(name="TZ", value="Europe/Zurich")], run_args.env)

    def test_prepare_run_args_adds_credential_forwarding(self) -> None:
        run_args = DockerRunArgs("image", "", [])
        mount = mock.Mock()
        env = EnvVar(
            name="SSH_AUTH_SOCK",
            value="/run/credential-agent/ssh-agent.sock",
        )
        config = self._run_config(ssh_enabled=True)
        parsed = ParsedArgs(False, "", "codex", [], False, [])
        with (
            mock.patch(
                "aicage.runtime.run_plan._build_run_args", return_value=run_args
            ),
            mock.patch(
                "aicage.runtime.run_plan.credential_forwarding",
                return_value=nullcontext(([mount], [env])),
            ) as forwarding_mock,
        ):
            with prepare_run_args(config, parsed, mock.Mock()) as result:
                self.assertIs(run_args, result)
                self.assertEqual([mount], result.mounts)
                self.assertEqual([env], result.env)

        forwarding_mock.assert_called_once_with(mock.ANY)

    def test_prepare_run_args_uses_credential_forwarding_when_ssh_is_disabled(
        self,
    ) -> None:
        run_args = DockerRunArgs("image", "", [])
        config = self._run_config(ssh_enabled=False)
        parsed = ParsedArgs(False, "", "codex", [], False, [])
        with (
            mock.patch(
                "aicage.runtime.run_plan._build_run_args", return_value=run_args
            ),
            mock.patch(
                "aicage.runtime.run_plan.credential_forwarding",
                return_value=nullcontext(([], [])),
            ) as forwarding_mock,
        ):
            with prepare_run_args(config, parsed, mock.Mock()) as result:
                self.assertIs(run_args, result)

        forwarding_mock.assert_called_once_with(mock.ANY)

    def test_host_timezone_env_uses_existing_tz_env(self) -> None:
        with mock.patch.dict(os.environ, {"TZ": "Europe/Zurich"}, clear=True):
            result = _host_timezone_env([])

        self.assertEqual([EnvVar(name="TZ", value="Europe/Zurich")], result)

    def test_host_timezone_env_skips_when_config_already_sets_tz(self) -> None:
        result = _host_timezone_env([EnvVar(name="TZ", value="UTC")])

        self.assertEqual([], result)

    def _run_config(self, *, ssh_enabled: bool) -> RunConfig:
        project_path = Path("/test-tmp/project")
        return RunConfig(
            project_path=project_path,
            agent="codex",
            context=ConfigContext(
                store=mock.Mock(),
                project_cfg=_ProjectConfig(
                    path=str(project_path),
                    agents={"codex": AgentConfig(mounts=_AgentMounts(ssh=ssh_enabled))},
                ),
                agents=self._get_agents(),
                bases=self._get_bases(),
                extensions={},
            ),
            selection=ImageSelection(
                image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
                base="ubuntu",
                extensions=[],
                agent_image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
            ),
            project_docker_args="",
            mounts=[],
            env=[],
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
