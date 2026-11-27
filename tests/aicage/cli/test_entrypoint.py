import io
import tempfile
from contextlib import nullcontext
from pathlib import Path
from unittest import TestCase, mock

from aicage.cli.entrypoint import main
from aicage.cli_types import (
    ConfigInfoArgs,
    ConfigRemoveArgs,
    ConfigUpdateArgs,
    ParsedArgs,
)
from aicage.config.agent.models import AgentMetadata
from aicage.config.base.models import BaseMetadata
from aicage.config.context import ConfigContext
from aicage.config.project_config import _ProjectConfig
from aicage.config.runtime_config import RunConfig
from aicage.registry.image_selection.models import ImageSelection
from aicage.runtime.run_args import DockerRunArgs


def _build_run_args(
    image_ref: str, merged_docker_args: str, agent_args: list[str]
) -> DockerRunArgs:
    return DockerRunArgs(
        image_ref=image_ref,
        merged_docker_args=merged_docker_args,
        agent_args=agent_args,
    )


def _build_run_config(project_path: Path, image_ref: str) -> RunConfig:
    bases, agents = _build_agents_and_bases()
    return RunConfig(
        project_path=project_path,
        agent="codex",
        context=ConfigContext(
            store=mock.Mock(),
            project_cfg=_ProjectConfig(path=str(project_path), agents={}),
            agents=agents,
            bases=bases,
            extensions={},
        ),
        selection=ImageSelection(
            image_ref=image_ref,
            base="ubuntu",
            extensions=[],
            agent_image_ref=image_ref,
        ),
        project_docker_args="--project",
        mounts=[],
        env=[],
    )


def _build_agents_and_bases() -> (
    tuple[dict[str, BaseMetadata], dict[str, AgentMetadata]]
):
    bases = {
        "alpine": BaseMetadata(
            from_image="alpine:latest",
            base_image_distro="Alpine",
            base_image_description="Minimal",
            architectures=["amd64", "arm64"],
            build_local=False,
            local_definition_dir=Path("/test-tmp/alpine"),
        ),
        "debian": BaseMetadata(
            from_image="debian:latest",
            base_image_distro="Debian",
            base_image_description="Default",
            architectures=["amd64", "arm64"],
            build_local=False,
            local_definition_dir=Path("/test-tmp/debian"),
        ),
        "ubuntu": BaseMetadata(
            from_image="ubuntu:latest",
            base_image_distro="Ubuntu",
            base_image_description="Default",
            architectures=["amd64", "arm64"],
            build_local=False,
            local_definition_dir=Path("/test-tmp/ubuntu"),
        ),
    }
    agents = {
        "codex": AgentMetadata(
            agent_path_files=[],
            agent_path_directories=["~/.codex"],
            agent_full_name="Codex CLI",
            agent_homepage="https://example.com",
            build_local=False,
            valid_bases={
                "alpine": "ghcr.io/aicage/aicage:codex-alpine",
                "debian": "ghcr.io/aicage/aicage:codex-debian",
                "ubuntu": "ghcr.io/aicage/aicage:codex-ubuntu",
            },
            local_definition_dir=Path("/test-tmp/codex"),
        )
    }
    return bases, agents


class EntrypointTests(TestCase):
    def test_main_config_info(self) -> None:
        with (
            mock.patch(
                "aicage.cli.entrypoint.parse_cli",
                return_value=ConfigInfoArgs(scope=None),
            ),
            mock.patch("aicage.cli.entrypoint.info_project_config") as info_mock,
            mock.patch("aicage.cli.entrypoint.load_run_config") as load_mock,
            mock.patch("aicage.cli.entrypoint.maybe_prompt_update") as update_mock,
            mock.patch(
                "aicage.cli.entrypoint.create_runtime_interaction"
            ) as create_interaction_mock,
        ):
            exit_code = main([])

        self.assertEqual(0, exit_code)
        create_interaction_mock.assert_not_called()
        update_mock.assert_not_called()
        info_mock.assert_called_once()
        load_mock.assert_not_called()

    def test_main_config_info_global(self) -> None:
        with (
            mock.patch(
                "aicage.cli.entrypoint.parse_cli",
                return_value=ConfigInfoArgs(scope="global"),
            ),
            mock.patch("aicage.cli.entrypoint.info_project_config") as info_mock,
            mock.patch("aicage.cli.entrypoint.maybe_prompt_update") as update_mock,
            mock.patch(
                "aicage.cli.entrypoint.create_runtime_interaction"
            ) as interaction_mock,
        ):
            exit_code = main([])

        self.assertEqual(0, exit_code)
        info_mock.assert_called_once_with("global")
        update_mock.assert_not_called()
        interaction_mock.assert_not_called()

    def test_main_skips_ensure_for_ui_menu(self) -> None:
        run_config = _build_run_config(Path("/test-tmp/project"), "repo:tag")
        interaction = mock.Mock()

        with (
            mock.patch(
                "aicage.cli.entrypoint.parse_cli",
                return_value=ParsedArgs(False, "", "codex", [], False, [], "ui"),
            ),
            mock.patch("aicage.cli.entrypoint.maybe_prompt_update", return_value=False),
            mock.patch(
                "aicage.cli.entrypoint.create_runtime_interaction",
                return_value=interaction,
            ) as create_interaction_mock,
            mock.patch(
                "aicage.cli.entrypoint.load_run_config", return_value=run_config
            ),
            mock.patch(
                "aicage.cli.entrypoint.prepare_run_args",
                return_value=nullcontext(_build_run_args("repo:tag", "", [])),
            ),
            mock.patch("aicage.cli.entrypoint.prepare_image") as prepare_image_mock,
            mock.patch("aicage.cli.entrypoint.run_container") as run_container_mock,
        ):
            exit_code = main(["codex"])

        self.assertEqual(0, exit_code)
        create_interaction_mock.assert_called_once_with("ui")
        prepare_image_mock.assert_called_once_with(run_config, interaction)
        run_container_mock.assert_called_once()

    def test_main_prepares_credential_image_before_credentials(self) -> None:
        run_config = _build_run_config(Path("/test-tmp/project"), "repo:tag")
        interaction = mock.Mock()
        credential_plan = mock.Mock()
        credentials = mock.Mock()
        calls: list[str] = []

        def plan_credentials(*_args: object) -> mock.Mock:
            calls.append("plan")
            return credential_plan

        def prepare_credential_image(*_args: object) -> None:
            calls.append("credential image")

        def prepare_credentials(*_args: object, **_kwargs: object) -> mock.Mock:
            calls.append("credentials")
            return credentials

        def prepare_image(*_args: object) -> None:
            calls.append("target image")

        with (
            mock.patch(
                "aicage.cli.entrypoint.parse_cli",
                return_value=ParsedArgs(False, "", "codex", [], False, [], "ui"),
            ),
            mock.patch("aicage.cli.entrypoint.maybe_prompt_update", return_value=False),
            mock.patch(
                "aicage.cli.entrypoint.create_runtime_interaction",
                return_value=interaction,
            ),
            mock.patch(
                "aicage.cli.entrypoint.load_run_config", return_value=run_config
            ),
            mock.patch(
                "aicage.cli.entrypoint.plan_credentials",
                side_effect=plan_credentials,
            ),
            mock.patch(
                "aicage.cli.entrypoint.prepare_credential_image",
                side_effect=prepare_credential_image,
            ),
            mock.patch(
                "aicage.cli.entrypoint.prepare_credentials",
                side_effect=prepare_credentials,
            ),
            mock.patch(
                "aicage.cli.entrypoint.prepare_image",
                side_effect=prepare_image,
            ),
            mock.patch(
                "aicage.cli.entrypoint.prepare_run_args",
                return_value=nullcontext(_build_run_args("repo:tag", "", [])),
            ),
            mock.patch("aicage.cli.entrypoint.run_container"),
        ):
            exit_code = main(["codex"])

        self.assertEqual(0, exit_code)
        self.assertEqual(
            ["plan", "credential image", "credentials", "target image"], calls
        )

    def test_main_config_remove_with_agent(self) -> None:
        with (
            mock.patch(
                "aicage.cli.entrypoint.parse_cli",
                return_value=ConfigRemoveArgs("codex", None),
            ),
            mock.patch("aicage.cli.entrypoint.remove_agent_config") as remove_mock,
            mock.patch("aicage.cli.entrypoint.load_run_config") as load_mock,
            mock.patch("aicage.cli.entrypoint.maybe_prompt_update") as update_mock,
            mock.patch(
                "aicage.cli.entrypoint.create_runtime_interaction"
            ) as create_interaction_mock,
        ):
            exit_code = main([])

        self.assertEqual(0, exit_code)
        create_interaction_mock.assert_not_called()
        update_mock.assert_not_called()
        remove_mock.assert_called_once_with("codex", None)
        load_mock.assert_not_called()

    def test_main_config_global_passes_parsed_values_without_running_image_setup(
        self,
    ) -> None:
        parsed = ConfigUpdateArgs(
            False,
            "-e GLOBAL_VAR=0",
            "codex",
            [],
            False,
            [],
            "none",
            scope="global",
        )
        interaction = mock.Mock()
        with (
            mock.patch("aicage.cli.entrypoint.parse_cli", return_value=parsed),
            mock.patch("aicage.cli.entrypoint.maybe_prompt_update", return_value=False),
            mock.patch(
                "aicage.cli.entrypoint.create_runtime_interaction",
                return_value=interaction,
            ),
            mock.patch(
                "aicage.cli.entrypoint.configure_inherited_config"
            ) as configure_mock,
            mock.patch("aicage.cli.entrypoint.prepare_image") as prepare_image_mock,
        ):
            exit_code = main([])

        self.assertEqual(0, exit_code)
        configure_mock.assert_called_once_with("global", "codex", interaction, parsed)
        prepare_image_mock.assert_not_called()

    def test_main_uses_project_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir)
            run_config = _build_run_config(
                project_path,
                "ghcr.io/aicage/aicage:codex-debian",
            )
            run_args = _build_run_args(
                "ghcr.io/aicage/aicage:codex-debian",
                "--project --cli",
                ["--flag"],
            )
            interaction = mock.Mock()
            with (
                mock.patch(
                    "aicage.cli.entrypoint.parse_cli",
                    return_value=ParsedArgs(
                        False, "--cli", "codex", ["--flag"], False, [], "ui"
                    ),
                ),
                mock.patch(
                    "aicage.cli.entrypoint.maybe_prompt_update", return_value=False
                ),
                mock.patch(
                    "aicage.cli.entrypoint.create_runtime_interaction",
                    return_value=interaction,
                ),
                mock.patch(
                    "aicage.cli.entrypoint.load_run_config", return_value=run_config
                ),
                mock.patch(
                    "aicage.cli.entrypoint.prepare_run_args",
                    return_value=nullcontext(run_args),
                ),
                mock.patch("aicage.cli.entrypoint.prepare_image") as prepare_image_mock,
                mock.patch("aicage.cli.entrypoint.run_container") as run_mock,
            ):
                exit_code = main([])

            self.assertEqual(0, exit_code)
            prepare_image_mock.assert_called_once_with(run_config, interaction)
            run_mock.assert_called_once_with(run_args)

    def test_main_prompts_and_saves_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir)
            run_config = _build_run_config(
                project_path,
                "ghcr.io/aicage/aicage:codex-alpine",
            )
            run_args = _build_run_args(
                "ghcr.io/aicage/aicage:codex-alpine",
                "--project --cli",
                ["--flag"],
            )
            interaction = mock.Mock()
            with (
                mock.patch(
                    "aicage.cli.entrypoint.parse_cli",
                    return_value=ParsedArgs(
                        False, "--cli", "codex", ["--flag"], False, [], "ui"
                    ),
                ),
                mock.patch(
                    "aicage.cli.entrypoint.maybe_prompt_update", return_value=False
                ),
                mock.patch(
                    "aicage.cli.entrypoint.create_runtime_interaction",
                    return_value=interaction,
                ),
                mock.patch(
                    "aicage.cli.entrypoint.load_run_config", return_value=run_config
                ),
                mock.patch(
                    "aicage.cli.entrypoint.prepare_run_args",
                    return_value=nullcontext(run_args),
                ),
                mock.patch("aicage.cli.entrypoint.prepare_image") as prepare_image_mock,
                mock.patch("aicage.cli.entrypoint.run_container"),
            ):
                exit_code = main([])

            self.assertEqual(0, exit_code)
            prepare_image_mock.assert_called_once_with(run_config, interaction)

    def test_main_handles_unexpected_exception(self) -> None:
        logger = mock.Mock()
        with (
            mock.patch(
                "aicage.cli.entrypoint.parse_cli",
                return_value=ParsedArgs(
                    False, "--cli", "codex", ["--flag"], False, [], "ui"
                ),
            ),
            mock.patch("aicage.cli.entrypoint.get_logger", return_value=logger),
            mock.patch("aicage.cli.entrypoint.maybe_prompt_update", return_value=False),
            mock.patch(
                "aicage.cli.entrypoint.load_run_config",
                side_effect=TimeoutError("The read operation timed out"),
            ),
            mock.patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main([])

        self.assertEqual(1, exit_code)
        self.assertIn(
            "[aicage] TimeoutError: The read operation timed out",
            stderr.getvalue(),
        )
        self.assertIn(
            "[aicage] More details in log: ",
            stderr.getvalue(),
        )
        logger.exception.assert_called_once_with(
            "Unhandled exception during CLI execution"
        )

    def test_main_handles_unexpected_exception_without_message(self) -> None:
        logger = mock.Mock()
        with (
            mock.patch(
                "aicage.cli.entrypoint.parse_cli",
                return_value=ParsedArgs(
                    False, "--cli", "codex", ["--flag"], False, [], "ui"
                ),
            ),
            mock.patch("aicage.cli.entrypoint.get_logger", return_value=logger),
            mock.patch("aicage.cli.entrypoint.maybe_prompt_update", return_value=False),
            mock.patch(
                "aicage.cli.entrypoint.load_run_config", side_effect=RuntimeError()
            ),
            mock.patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main([])

        self.assertEqual(1, exit_code)
        self.assertIn("[aicage] RuntimeError", stderr.getvalue())
        logger.exception.assert_called_once_with(
            "Unhandled exception during CLI execution"
        )
