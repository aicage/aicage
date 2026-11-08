import tempfile
from pathlib import Path
from unittest import TestCase, mock

from aicage.runtime import _ssh_agent

_MODULE = "aicage.runtime._ssh_agent"


class SshAgentTests(TestCase):
    def test_resolve_ssh_key_files_includes_ssh_and_configured_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            ssh_dir = root / ".ssh"
            ssh_dir.mkdir()
            default_key = ssh_dir / "id_ed25519"
            default_key.touch()
            external_key = root / "work-key"
            external_key.touch()
            config_dir = ssh_dir / "config.d"
            config_dir.mkdir()
            included = config_dir / "work"
            included.write_text(f"IdentityFile {external_key}\n", encoding="utf-8")
            (ssh_dir / "config").write_text(
                f"Include config.d/*\nIdentityFile {default_key}\n", encoding="utf-8"
            )
            (ssh_dir / "known_hosts").touch()
            (ssh_dir / "id_ed25519.pub").touch()
            external_key.with_name("work-key.pub").touch()

            with mock.patch(f"{_MODULE}.HOST_SSH_DIR", ssh_dir):
                keys = _ssh_agent._resolve_ssh_key_files()
                support_files = _ssh_agent._resolve_ssh_support_files()

        self.assertEqual([default_key, external_key], keys)
        self.assertEqual(
            [
                ssh_dir / "config",
                included,
                ssh_dir / "known_hosts",
                ssh_dir / "id_ed25519.pub",
                external_key.with_name("work-key.pub"),
            ],
            support_files,
        )

    def test_has_ssh_keys_uses_private_key_files(self) -> None:
        with mock.patch(
            f"{_MODULE}._resolve_ssh_key_files", return_value=[Path("key")]
        ):
            self.assertTrue(_ssh_agent._has_ssh_keys())
        with mock.patch(f"{_MODULE}._resolve_ssh_key_files", return_value=[]):
            self.assertFalse(_ssh_agent._has_ssh_keys())

    def test_config_values_preserves_windows_identity_file_backslashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = Path(tmp_dir) / "config"
            config.write_text(
                "IdentityFile C:\\Users\\runner\\.ssh\\work-key\n",
                encoding="utf-8",
            )
            with mock.patch(f"{_MODULE}.os.name", "nt"):
                values = _ssh_agent._config_values(config, "IdentityFile")

        self.assertEqual([r"C:\Users\runner\.ssh\work-key"], values)
