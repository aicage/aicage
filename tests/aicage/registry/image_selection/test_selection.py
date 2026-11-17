import tempfile
from pathlib import Path
from unittest import TestCase, mock

from aicage.config.config_store import SettingsStore
from aicage.config.context import ConfigContext
from aicage.config.extensions.loader import ExtensionMetadata
from aicage.config.image_refs import default_extended_image_ref, local_image_ref
from aicage.config.project_config import AgentConfig, _ProjectConfig
from aicage.constants import (
    DEFAULT_EXTENDED_IMAGE_NAME,
    IMAGE_REGISTRY,
    IMAGE_REPOSITORY,
    LOCAL_IMAGE_REPOSITORY,
)
from aicage.registry._errors import RegistryError
from aicage.registry.image_selection.models import ImageSelection
from aicage.registry.image_selection.selection import select_agent_image

from ._fixtures import build_agents_and_bases, build_context


class ImageSelectionTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._extensions: dict[str, ExtensionMetadata] = {}

    def test_select_agent_image_uses_existing_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir) / "project"
            project_path.mkdir()
            store = mock.Mock(spec=SettingsStore)
            context = build_context(store, project_path, bases=["debian", "ubuntu"])
            context.project_cfg.agents["codex"] = AgentConfig(base="debian")
            selection = select_agent_image("codex", context, mock.Mock())

            self.assertEqual(
                f"{IMAGE_REGISTRY}/{IMAGE_REPOSITORY}:codex-debian", selection.image_ref
            )
            store.save_project.assert_not_called()

    def test_select_agent_image_prompts_and_marks_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir) / "project"
            project_path.mkdir()
            store = mock.Mock(spec=SettingsStore)
            context = build_context(store, project_path, bases=["alpine", "ubuntu"])
            with (
                mock.patch(
                    "aicage.config.extended_images.IMAGE_EXTENDED_STATE_DIR",
                    Path(tmp_dir) / "extended-images",
                ),
                mock.patch(
                    "aicage.registry.image_selection._fresh_selection.handle_extension_selection",
                    return_value="alpine",
                ),
            ):
                select_agent_image("codex", context, _selection_interaction())

            self.assertEqual("alpine", context.project_cfg.agents["codex"].base)
            store.save_project.assert_not_called()

    def test_select_agent_image_raises_without_bases(self) -> None:
        context = build_context(
            mock.Mock(spec=SettingsStore), Path("/test-tmp/project"), bases=[]
        )
        with self.assertRaises(RegistryError):
            select_agent_image("codex", context, mock.Mock())

    def test_select_agent_image_raises_on_invalid_base(self) -> None:
        context = build_context(
            mock.Mock(spec=SettingsStore),
            Path("/test-tmp/project"),
            bases=["ubuntu"],
            agents={"codex": AgentConfig(base="alpine")},
        )
        with self.assertRaises(RegistryError):
            select_agent_image("codex", context, mock.Mock())

    def test_select_agent_image_build_local_uses_local_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir) / "project"
            project_path.mkdir()
            store = mock.Mock(spec=SettingsStore)
            bases, agents = build_agents_and_bases(
                ["ubuntu"],
                agent_name="claude",
                build_local=True,
            )
            context = ConfigContext(
                store=store,
                project_cfg=_ProjectConfig(path=str(project_path), agents={}),
                agents=agents,
                bases=bases,
                extensions=self._extensions,
            )
            context.project_cfg.agents["claude"] = AgentConfig(base="ubuntu")
            selection = select_agent_image("claude", context, mock.Mock())

            self.assertEqual(
                local_image_ref(LOCAL_IMAGE_REPOSITORY, "claude", "ubuntu"),
                selection.image_ref,
            )
            store.save_project.assert_not_called()

    @staticmethod
    def test_select_agent_image_uses_fresh_selection_when_image_ref_has_no_base() -> (
        None
    ):
        context = build_context(
            mock.Mock(spec=SettingsStore), Path("/test-tmp/project"), bases=["ubuntu"]
        )
        agent_cfg = AgentConfig(image_ref="aicage:codex-ubuntu")
        context.project_cfg.agents["codex"] = agent_cfg
        with mock.patch(
            "aicage.registry.image_selection.selection.fresh_selection",
            return_value=ImageSelection(
                image_ref="aicage:codex-ubuntu",
                base="ubuntu",
                extensions=[],
                agent_image_ref=f"{IMAGE_REGISTRY}/{IMAGE_REPOSITORY}:codex-ubuntu",
            ),
        ) as fresh_mock:
            select_agent_image("codex", context, mock.Mock())
        fresh_mock.assert_called_once()

    def test_select_agent_image_uses_stored_image_ref(self) -> None:
        context = build_context(
            mock.Mock(spec=SettingsStore), Path("/test-tmp/project"), bases=["ubuntu"]
        )
        agent_cfg = AgentConfig(
            base="ubuntu", image_ref="aicage:codex-ubuntu", extensions=[]
        )
        context.project_cfg.agents["codex"] = agent_cfg
        selection = select_agent_image("codex", context, mock.Mock())
        self.assertEqual("aicage:codex-ubuntu", selection.image_ref)

    def test_select_agent_image_ignores_stale_extended_image_ref(self) -> None:
        context = build_context(
            mock.Mock(spec=SettingsStore), Path("/test-tmp/project"), bases=["ubuntu"]
        )
        agent_cfg = AgentConfig(
            base="ubuntu",
            image_ref=f"{DEFAULT_EXTENDED_IMAGE_NAME}:codex-ubuntu-regctl",
        )
        context.project_cfg.agents["codex"] = agent_cfg

        selection = select_agent_image("codex", context, _selection_interaction())

        self.assertEqual(
            f"{IMAGE_REGISTRY}/{IMAGE_REPOSITORY}:codex-ubuntu", selection.image_ref
        )
        self.assertEqual(selection.image_ref, agent_cfg.image_ref)

    def test_select_agent_image_recalculates_extended_image_ref(self) -> None:
        context = build_context(
            mock.Mock(spec=SettingsStore), Path("/test-tmp/project"), bases=["ubuntu"]
        )
        context.extensions["regctl"] = ExtensionMetadata(
            extension_id="regctl",
            name="regctl",
            description="Registry CLI",
            shares=[],
            directory=Path("/test-tmp/regctl"),
            scripts_dir=Path("/test-tmp/regctl/scripts"),
            dockerfile_path=None,
        )
        agent_cfg = AgentConfig(
            base="ubuntu",
            image_ref="aicage-extended:codex-ubuntu-regctl",
            extensions=["regctl"],
        )
        context.project_cfg.agents["codex"] = agent_cfg

        selection = select_agent_image("codex", context, mock.Mock())

        expected_image_ref = default_extended_image_ref(
            "codex", "ubuntu", ["regctl"], context.extensions
        )
        self.assertEqual(expected_image_ref, selection.image_ref)
        self.assertEqual(expected_image_ref, agent_cfg.image_ref)

    def test_select_agent_image_raises_when_agent_missing(self) -> None:
        context = ConfigContext(
            store=mock.Mock(spec=SettingsStore),
            project_cfg=_ProjectConfig(path="/test-tmp/project", agents={}),
            agents={},
            bases={},
            extensions=self._extensions,
        )
        with self.assertRaises(RegistryError):
            select_agent_image("codex", context, mock.Mock())


def _selection_interaction() -> mock.Mock:
    interaction = mock.Mock()
    interaction.choose_base.return_value = "alpine"
    interaction.choose_extensions.return_value = []
    return interaction
