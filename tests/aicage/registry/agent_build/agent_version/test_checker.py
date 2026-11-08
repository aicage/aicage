import tempfile
from pathlib import Path
from unittest import TestCase, mock

import yaml

from aicage.config.agent.models import AgentMetadata
from aicage.constants import VERSION_CHECK_IMAGE
from aicage.registry._errors import RegistryError
from aicage.registry.agent_build.agent_version import _command as command
from aicage.registry.agent_build.agent_version._store import _VERSION_KEY
from aicage.registry.agent_build.agent_version.checker import AgentVersionChecker


class AgentVersionCheckTests(TestCase):
    def test_get_version_uses_host_success_and_persists(self) -> None:
        reporter = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent_dir = Path(tmp_dir) / "custom"
            agent_dir.mkdir()
            (agent_dir / "version.sh").write_text("echo 1.2.3\n", encoding="utf-8")
            store_dir = Path(tmp_dir) / "state"

            with (
                mock.patch(
                    "aicage.registry.agent_build.agent_version._store.paths_module.AGENT_VERSION_CHECK_STATE_DIR",
                    store_dir,
                ),
                mock.patch(
                    "aicage.registry.agent_build.agent_version.checker.run_host",
                    return_value=command._CommandResult(
                        success=True, output="1.2.3", error=""
                    ),
                ),
            ):
                checker = AgentVersionChecker()
                result = checker.get_version(
                    "custom",
                    self._agent_metadata(),
                    definition_dir=agent_dir,
                    reporter=reporter,
                )

            self.assertEqual("1.2.3", result)
            stored = store_dir / "custom.yml"
            self.assertTrue(stored.is_file())
            data = yaml.safe_load(stored.read_text(encoding="utf-8"))
            self.assertEqual("1.2.3", data[_VERSION_KEY])

    def test_get_version_uses_version_check_image_and_persists(self) -> None:
        reporter = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent_dir = Path(tmp_dir) / "custom"
            agent_dir.mkdir()
            (agent_dir / "version.sh").write_text("echo 1.2.3\n", encoding="utf-8")
            store_dir = Path(tmp_dir) / "state"

            with (
                mock.patch(
                    "aicage.registry.agent_build.agent_version._store.paths_module.AGENT_VERSION_CHECK_STATE_DIR",
                    store_dir,
                ),
                mock.patch(
                    "aicage.registry.agent_build.agent_version.checker.run_host",
                    return_value=command._CommandResult(
                        success=False, output="", error="host failed"
                    ),
                ),
                mock.patch(
                    "aicage.registry.agent_build.agent_version.checker.run_version_check_image",
                    return_value=command._CommandResult(
                        success=True, output="1.2.3", error=""
                    ),
                ) as run_version_check_image_mock,
            ):
                checker = AgentVersionChecker()
                result = checker.get_version(
                    "custom",
                    self._agent_metadata(),
                    definition_dir=agent_dir,
                    reporter=reporter,
                )

            self.assertEqual("1.2.3", result)
            stored = store_dir / "custom.yml"
            self.assertTrue(stored.is_file())
            data = yaml.safe_load(stored.read_text(encoding="utf-8"))
            self.assertEqual("1.2.3", data[_VERSION_KEY])
            run_version_check_image_mock.assert_called_once_with(
                VERSION_CHECK_IMAGE,
                agent_dir,
                reporter=reporter,
            )

    def test_get_version_raises_when_version_check_image_fails(self) -> None:
        reporter = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent_dir = Path(tmp_dir) / "custom"
            agent_dir.mkdir()
            (agent_dir / "version.sh").write_text("echo 1.2.3\n", encoding="utf-8")
            store_dir = Path(tmp_dir) / "state"

            with (
                mock.patch(
                    "aicage.registry.agent_build.agent_version._store.paths_module.AGENT_VERSION_CHECK_STATE_DIR",
                    store_dir,
                ),
                mock.patch(
                    "aicage.registry.agent_build.agent_version.checker.run_host",
                    return_value=command._CommandResult(
                        success=False, output="", error="host failed"
                    ),
                ),
                mock.patch(
                    "aicage.registry.agent_build.agent_version.checker.run_version_check_image",
                    return_value=command._CommandResult(
                        success=False,
                        output="",
                        error="version check failed",
                    ),
                ) as run_version_check_image_mock,
            ):
                checker = AgentVersionChecker()
                with self.assertRaises(RegistryError) as raised:
                    checker.get_version(
                        "custom",
                        self._agent_metadata(build_local=False),
                        definition_dir=agent_dir,
                        reporter=reporter,
                    )
            self.assertIn("version check failed", str(raised.exception))
            run_version_check_image_mock.assert_called_once_with(
                VERSION_CHECK_IMAGE,
                agent_dir,
                reporter=reporter,
            )

    def test_get_version_uses_cached_version_for_local_agent_when_offline(self) -> None:
        reporter = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent_dir = Path(tmp_dir) / "custom"
            agent_dir.mkdir()
            (agent_dir / "version.sh").write_text("echo 1.2.3\n", encoding="utf-8")
            store_dir = Path(tmp_dir) / "state"
            cached_path = store_dir / "custom.yml"
            cached_path.parent.mkdir(parents=True, exist_ok=True)
            cached_path.write_text(
                yaml.safe_dump(
                    {
                        "agent": "custom",
                        "version": "9.9.9",
                        "checked_at": "2026-01-01T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )

            with (
                mock.patch(
                    "aicage.registry.agent_build.agent_version._store.paths_module.AGENT_VERSION_CHECK_STATE_DIR",
                    store_dir,
                ),
                mock.patch(
                    "aicage.registry.agent_build.agent_version.checker.run_host",
                    return_value=command._CommandResult(
                        success=False, output="", error="host failed"
                    ),
                ),
                mock.patch(
                    "aicage.registry.agent_build.agent_version.checker.run_version_check_image"
                ) as image_check_mock,
            ):
                image_check_mock.return_value = command._CommandResult(
                    success=False,
                    output="",
                    error="offline",
                )
                checker = AgentVersionChecker()
                result = checker.get_version(
                    "custom",
                    self._agent_metadata(),
                    definition_dir=agent_dir,
                    reporter=reporter,
                )

            self.assertEqual("9.9.9", result)
            image_check_mock.assert_called_once_with(
                VERSION_CHECK_IMAGE,
                agent_dir,
                reporter=reporter,
            )

    def test_get_version_raises_on_missing_version_script(self) -> None:
        reporter = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent_dir = Path(tmp_dir) / "custom"
            agent_dir.mkdir()
            store_dir = Path(tmp_dir) / "state"
            with mock.patch(
                "aicage.registry.agent_build.agent_version._store.paths_module.AGENT_VERSION_CHECK_STATE_DIR",
                store_dir,
            ):
                checker = AgentVersionChecker()
                with self.assertRaises(RegistryError):
                    checker.get_version(
                        "custom",
                        self._agent_metadata(),
                        definition_dir=agent_dir,
                        reporter=reporter,
                    )
            self.assertFalse((store_dir / "custom.yml").exists())

    @staticmethod
    def _agent_metadata(build_local: bool = True) -> AgentMetadata:
        return AgentMetadata(
            agent_path_files=[],
            agent_path_directories=["~/.custom"],
            agent_full_name="Custom",
            agent_homepage="https://example.com",
            build_local=build_local,
            valid_bases={},
            local_definition_dir=Path("/test-tmp/definition"),
        )
