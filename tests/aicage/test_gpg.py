import tempfile
from pathlib import Path
from unittest import TestCase, mock

from aicage import gpg
from aicage.paths import HOST_GNUPG_DIR

_MODULE = "aicage.gpg"


class GpgTests(TestCase):
    def test_resolve_gpg_home_handles_missing_directory(self) -> None:
        with (
            mock.patch(f"{_MODULE}._capture_stdout", return_value=""),
            mock.patch(f"{_MODULE}.HOST_GNUPG_DIR", Path("/missing")),
        ):
            self.assertIsNone(gpg.resolve_gpg_home())

    def test_resolve_gpg_home_falls_back_when_gpgconf_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            gpg_home = Path(tmp_dir) / ".gnupg"
            gpg_home.mkdir()
            with (
                mock.patch(f"{_MODULE}.HOST_GNUPG_DIR", gpg_home),
                mock.patch(f"{_MODULE}.subprocess.run", side_effect=FileNotFoundError),
            ):
                self.assertEqual(gpg_home, gpg.resolve_gpg_home())

    def test_resolve_gpg_public_files_returns_existing_files(self) -> None:
        with mock.patch("pathlib.Path.is_file", return_value=False):
            self.assertEqual([], gpg.resolve_gpg_public_files(Path("/test-tmp/gnupg")))

    def test_has_gpg_keys_skips_lookup_without_gpg_home(self) -> None:
        with (
            mock.patch(f"{_MODULE}.resolve_gpg_home", return_value=None),
            mock.patch(
                f"{_MODULE}._resolve_gpg_secret_key_fingerprints"
            ) as resolve_keys,
        ):
            self.assertFalse(gpg.has_gpg_keys())
        resolve_keys.assert_not_called()

    def test_resolve_gpg_home_parses_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            gpg_home = Path(tmp_dir) / HOST_GNUPG_DIR.name
            gpg_home.mkdir()
            with mock.patch(
                f"{_MODULE}._capture_stdout",
                return_value=f"{gpg_home}\n",
            ):
                path = gpg.resolve_gpg_home()
        self.assertEqual(gpg_home, path)

    def test_resolve_gpg_home_falls_back_to_home_gnupg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            gpg_home = Path(tmp_dir) / HOST_GNUPG_DIR.name
            gpg_home.mkdir()
            with (
                mock.patch(f"{_MODULE}.HOST_GNUPG_DIR", gpg_home),
                mock.patch(f"{_MODULE}._capture_stdout", return_value=""),
            ):
                path = gpg.resolve_gpg_home()
        self.assertEqual(gpg_home, path)

    def test_resolve_gpg_home_handles_missing_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                mock.patch(
                    f"{_MODULE}.HOST_GNUPG_DIR", Path(tmp_dir) / HOST_GNUPG_DIR.name
                ),
                mock.patch(f"{_MODULE}._capture_stdout", return_value=""),
            ):
                path = gpg.resolve_gpg_home()
        self.assertIsNone(path)

    def test_resolve_gpg_agent_socket_parses_output(self) -> None:
        socket_path = Path("/test-tmp/S.gpg-agent")
        with mock.patch(
            f"{_MODULE}._capture_stdout",
            return_value=f"{socket_path}\n",
        ):
            path = gpg.resolve_gpg_agent_socket()
        self.assertEqual(socket_path, path)

    def test_resolve_gpg_public_files_returns_default_and_configured_files(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            gpg_home = Path(tmp_dir) / "gnupg"
            gpg_home.mkdir()
            common_conf = gpg_home / "common.conf"
            (gpg_home / "pubring.kbx").touch()
            keyboxd_database = gpg_home / "public-keys.d" / "pubring.db"
            keyboxd_database.parent.mkdir()
            keyboxd_database.touch()
            (gpg_home / "trustdb.gpg").touch()
            custom_keyring = gpg_home / "custom.kbx"
            custom_keyring.touch()
            common_conf.write_text("use-keyboxd\n", encoding="utf-8")
            gpg_conf = gpg_home / "gpg.conf"
            gpg_conf.write_text(
                "keyring custom.kbx\ntrustdb-name missing-trustdb.gpg\n",
                encoding="utf-8",
            )

            paths = gpg.resolve_gpg_public_files(gpg_home)

        self.assertEqual(
            [
                common_conf,
                gpg_conf,
                gpg_home / "pubring.kbx",
                keyboxd_database,
                gpg_home / "trustdb.gpg",
                custom_keyring,
            ],
            paths,
        )

    def test_resolve_gpg_secret_key_fingerprints_returns_primary_keys(self) -> None:
        output = (
            "sec:u::::\n"
            "fpr:::::::::PRIMARY_ONE:\n"
            "ssb:u::::\n"
            "fpr:::::::::SUBKEY_ONE:\n"
            "sec:u::::\n"
            "fpr:::::::::PRIMARY_TWO:\n"
        )
        with mock.patch(f"{_MODULE}._capture_stdout", return_value=output) as capture:
            fingerprints = gpg._resolve_gpg_secret_key_fingerprints()

        self.assertEqual(["PRIMARY_ONE", "PRIMARY_TWO"], fingerprints)
        capture.assert_called_once_with(
            [
                "gpg",
                "--batch",
                "--with-colons",
                "--with-keygrip",
                "--list-secret-keys",
            ]
        )

    def test_resolve_gpg_secret_key_state_returns_primary_fingerprints_and_keygrips(
        self,
    ) -> None:
        output = (
            "sec:u::::\n"
            "fpr:::::::::PRIMARY:\n"
            "grp:::::::::KEYGRIP_ONE:\n"
            "ssb:u::::\n"
            "grp:::::::::KEYGRIP_TWO:\n"
        )
        with mock.patch(f"{_MODULE}._capture_stdout", return_value=output) as capture:
            fingerprints, keygrips = gpg.resolve_gpg_secret_key_state()

        self.assertEqual(["PRIMARY"], fingerprints)
        self.assertEqual({"KEYGRIP_ONE", "KEYGRIP_TWO"}, keygrips)
        capture.assert_called_once_with(
            [
                "gpg",
                "--batch",
                "--with-colons",
                "--with-keygrip",
                "--list-secret-keys",
            ]
        )

    def test_resolve_gpg_secret_key_state_skips_unusable_primary_keys(self) -> None:
        output = (
            "sec:e::::\n" "fpr:::::::::EXPIRED:\n" "sec:u::::\n" "fpr:::::::::USABLE:\n"
        )
        with mock.patch(f"{_MODULE}._capture_stdout", return_value=output):
            fingerprints, _keygrips = gpg.resolve_gpg_secret_key_state()

        self.assertEqual(["USABLE"], fingerprints)

    def test_has_gpg_keys_requires_a_secret_key(self) -> None:
        with (
            mock.patch(
                f"{_MODULE}.resolve_gpg_home", return_value=Path("/test-tmp/gnupg")
            ),
        ):
            self.assertFalse(gpg.has_gpg_keys())

    def test_has_gpg_keys_uses_the_private_key_directory_without_host_gpg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            gpg_home = Path(tmp_dir) / "gnupg"
            private_keys = gpg_home / "private-keys-v1.d"
            private_keys.mkdir(parents=True)
            (private_keys / "KEYGRIP.key").touch()
            with (
                mock.patch(f"{_MODULE}.resolve_gpg_home", return_value=gpg_home),
                mock.patch(f"{_MODULE}.subprocess.run") as run_mock,
            ):
                self.assertTrue(gpg.has_gpg_keys())

        run_mock.assert_not_called()
