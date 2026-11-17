import tempfile
from pathlib import Path
from unittest import TestCase, mock

from aicage.config.agent.models import AgentMetadata
from aicage.config.base.models import BaseMetadata
from aicage.config.context import ConfigContext
from aicage.config.extensions.loader import ExtensionMetadata
from aicage.config.project_config import AgentConfig, _ProjectConfig
from aicage.constants import (
    DEFAULT_EXTENDED_IMAGE_NAME,
    IMAGE_REGISTRY,
    IMAGE_REPOSITORY,
)
from aicage.registry.image_selection.extensions.context import ExtensionSelectionContext
from aicage.registry.image_selection.extensions.handler import (
    handle_extension_selection,
)


class ExtensionHandlerTests(TestCase):
    def test_handle_extension_selection_uses_base_when_none_selected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            save_project_mock = mock.Mock()
            context = self._context(tmp_dir, save_project_mock)
            agent_cfg = AgentConfig()
            selection = ExtensionSelectionContext(
                agent="codex",
                base="ubuntu",
                agent_cfg=agent_cfg,
                agent_metadata=self._agent_metadata(local=False),
                extensions={},
                context=context,
            )
            result = handle_extension_selection(selection, _selection_interaction([]))

            self.assertEqual(
                f"{IMAGE_REGISTRY}/{IMAGE_REPOSITORY}:codex-ubuntu", result.image_ref
            )
            self.assertEqual([], agent_cfg.extensions)
            save_project_mock.assert_not_called()

    def test_handle_extension_selection_persists_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            save_project_mock = mock.Mock()
            context = self._context(tmp_dir, save_project_mock)
            agent_cfg = AgentConfig()
            extension = self._extension(tmp_dir, "extra")
            selection = ExtensionSelectionContext(
                agent="codex",
                base="ubuntu",
                agent_cfg=agent_cfg,
                agent_metadata=self._agent_metadata(local=False),
                extensions={"extra": extension},
                context=context,
            )
            with (
                mock.patch(
                    "aicage.registry.image_selection.extensions.handler.write_extended_image_config"
                ) as write_mock,
            ):
                result = handle_extension_selection(
                    selection,
                    _selection_interaction(["extra"]),
                )

            self.assertEqual(
                f"{DEFAULT_EXTENDED_IMAGE_NAME}:codex-ubuntu-extra", result.image_ref
            )
            self.assertEqual(["extra"], agent_cfg.extensions)
            write_mock.assert_called_once()
            save_project_mock.assert_not_called()

    def test_handle_extension_selection_groups_script_extensions_before_dockerfiles(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            save_project_mock = mock.Mock()
            context = self._context(tmp_dir, save_project_mock)
            agent_cfg = AgentConfig()
            selection = ExtensionSelectionContext(
                agent="codex",
                base="ubuntu",
                agent_cfg=agent_cfg,
                agent_metadata=self._agent_metadata(local=False),
                extensions={
                    "zeta": self._extension(tmp_dir, "zeta", dockerfile=True),
                    "alpha": self._extension(tmp_dir, "alpha"),
                },
                context=context,
            )
            interaction = _selection_interaction(
                ["alpha", "zeta"],
            )

            handle_extension_selection(selection, interaction)

        self.assertEqual(["alpha", "zeta"], agent_cfg.extensions)
        self.assertEqual(
            ["alpha", "zeta"],
            [option.name for option in interaction.choose_extensions.call_args.args[0]],
        )

    @staticmethod
    def _extension(
        tmp_dir: str,
        extension_id: str,
        dockerfile: bool = False,
    ) -> ExtensionMetadata:
        base = Path(tmp_dir)
        return ExtensionMetadata(
            extension_id=extension_id,
            name=extension_id,
            description="desc",
            shares=[],
            directory=base,
            scripts_dir=base,
            dockerfile_path=base / "Dockerfile" if dockerfile else None,
        )

    @staticmethod
    def _agent_metadata(local: bool) -> AgentMetadata:
        return AgentMetadata(
            agent_path_files=[],
            agent_path_directories=["~/.codex"],
            agent_full_name="Codex",
            agent_homepage="https://example.com",
            build_local=local,
            valid_bases={"ubuntu": f"{IMAGE_REGISTRY}/{IMAGE_REPOSITORY}:codex-ubuntu"},
            local_definition_dir=Path("/test-tmp/def"),
        )

    @staticmethod
    def _context(tmp_dir: str, save_project_mock: mock.Mock) -> ConfigContext:
        bases = {
            "ubuntu": BaseMetadata(
                from_image="ubuntu:latest",
                base_image_distro="Ubuntu",
                base_image_description="Default",
                architectures=["amd64", "arm64"],
                build_local=False,
                local_definition_dir=Path("/test-tmp/ubuntu"),
            )
        }
        store = mock.Mock()
        store.save_project = save_project_mock
        return ConfigContext(
            store=store,
            project_cfg=_ProjectConfig(path=str(Path(tmp_dir) / "project"), agents={}),
            agents={},
            bases=bases,
            extensions={},
        )


def _selection_interaction(
    extensions: list[str],
) -> mock.Mock:
    interaction = mock.Mock()
    interaction.choose_extensions.return_value = extensions
    return interaction
