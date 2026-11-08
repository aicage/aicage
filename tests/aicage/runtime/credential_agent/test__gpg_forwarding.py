import tempfile
from contextlib import nullcontext
from pathlib import Path, PurePosixPath
from unittest import TestCase, mock

from aicage.docker.errors import DockerError
from aicage.paths import container_project_path
from aicage.runtime.credential_agent import _gpg_forwarding
from aicage.runtime.credential_agent._resource_models import (
    _CredentialProtocol,
    _resources,
)
from aicage.runtime.run_args import BindMountSpec, VolumeMountSpec


class GpgForwardingTests(TestCase):
    def test_gpg_forwarding_returns_none_without_a_home(self) -> None:
        with mock.patch.object(_gpg_forwarding, "resolve_gpg_home", return_value=None):
            self.assertIsNone(_gpg_forwarding._gpg_forwarding())

    def test_gpg_enabled_requires_mount_preference(self) -> None:
        context = mock.Mock()
        context.project_cfg.agents = {"codex": mock.Mock(mounts=mock.Mock(gnupg=True))}
        self.assertTrue(_gpg_forwarding._gpg_enabled(context, "codex"))

        context.project_cfg.agents["codex"].mounts.gnupg = False
        self.assertFalse(_gpg_forwarding._gpg_enabled(context, "codex"))

    def test_direct_gpg_socket_requires_a_reachable_unix_socket(self) -> None:
        socket = mock.Mock(spec=Path)
        socket.is_socket.return_value = True
        with (
            mock.patch.object(_gpg_forwarding.os, "name", "posix"),
            mock.patch.object(
                _gpg_forwarding, "resolve_gpg_agent_socket", return_value=socket
            ),
            mock.patch.object(
                _gpg_forwarding, "_GPG_CONNECT_AGENT", "/usr/bin/gpg-connect-agent"
            ),
            mock.patch.object(
                _gpg_forwarding.subprocess, "run", return_value=mock.Mock(returncode=0)
            ),
        ):
            self.assertIs(socket, _gpg_forwarding._direct_gpg_socket())

    def test_gpg_forwarding_uses_a_sidecar_without_a_direct_socket(self) -> None:
        home = Path("/test-tmp/gnupg")
        with (
            mock.patch.object(_gpg_forwarding, "resolve_gpg_home", return_value=home),
            mock.patch.object(
                _gpg_forwarding, "resolve_gpg_public_files"
            ) as public_files_mock,
            mock.patch.object(_gpg_forwarding, "_direct_gpg_socket", return_value=None),
        ):
            plan = _gpg_forwarding._gpg_forwarding()

        assert plan is not None
        self.assertTrue(plan.requires_sidecar)
        self.assertEqual(home, plan.credential_home)
        public_files_mock.assert_not_called()

    def test_direct_gpg_socket_rejects_windows_and_missing_sockets(self) -> None:
        with mock.patch.object(_gpg_forwarding.os, "name", "nt"):
            self.assertIsNone(_gpg_forwarding._direct_gpg_socket())

    def test_direct_gpg_socket_uses_the_sidecar_without_host_tools(self) -> None:
        with (
            mock.patch.object(_gpg_forwarding.os, "name", "posix"),
            mock.patch.object(_gpg_forwarding, "_GPG", None),
            mock.patch.object(_gpg_forwarding, "_GPG_CONNECT_AGENT", None),
            mock.patch.object(_gpg_forwarding.subprocess, "run") as run_mock,
        ):
            self.assertIsNone(_gpg_forwarding._direct_gpg_socket())

        run_mock.assert_not_called()

    def test_sidecar_target_args_uses_a_private_client_home(self) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            gpg_home = parent / "gnupg"
            gpg_home.mkdir()
            public_keyring = gpg_home / "pubring.kbx"
            external_keyring = parent / "external.kbx"
            public_keyring.write_text("public keyring", encoding="utf-8")
            external_keyring.write_text("external keyring", encoding="utf-8")
            with (
                mock.patch.object(
                    _gpg_forwarding,
                    "resolve_gpg_public_files",
                    return_value=[public_keyring, external_keyring],
                ),
                mock.patch.object(
                    Path,
                    "symlink_to",
                    side_effect=AssertionError(
                        "The host must not create the GnuPG socket link."
                    ),
                ),
            ):
                plan = _gpg_forwarding._GpgForwardingPlan(gpg_home, True)
                with plan.sidecar_target_args(resource) as mounts:
                    client_mount = mounts[0]
                    assert isinstance(client_mount, BindMountSpec)
                    client_home = client_mount.host_path
                    self.assertEqual(
                        "public keyring",
                        (client_home / "pubring.kbx").read_text(encoding="utf-8"),
                    )
                    self.assertFalse(
                        (client_home / _gpg_forwarding._GPG_SOCKET_NAME).is_symlink()
                    )
                    self.assertEqual(
                        [
                            BindMountSpec(
                                client_home,
                                _gpg_forwarding._GPG_STAGING_HOME,
                            ),
                            BindMountSpec(
                                external_keyring,
                                container_project_path(external_keyring),
                                True,
                            ),
                            VolumeMountSpec(
                                resource.volume_name,
                                _gpg_forwarding._GPG_SOCKET_DIRECTORY,
                                True,
                            ),
                        ],
                        mounts,
                    )
            self.assertFalse(client_home.exists())
        with (
            mock.patch.object(_gpg_forwarding.os, "name", "posix"),
            mock.patch.object(
                _gpg_forwarding, "resolve_gpg_agent_socket", return_value=None
            ),
        ):
            self.assertIsNone(_gpg_forwarding._direct_gpg_socket())

    def test_gpg_forwarding_uses_a_direct_socket(self) -> None:
        home = Path("/test-tmp/gnupg")
        socket = home / "S.gpg-agent"
        public_keyring = home / "pubring.kbx"
        with (
            mock.patch.object(_gpg_forwarding, "resolve_gpg_home", return_value=home),
            mock.patch.object(
                _gpg_forwarding,
                "resolve_gpg_public_files",
                return_value=[public_keyring],
            ),
            mock.patch.object(
                _gpg_forwarding, "_direct_gpg_socket", return_value=socket
            ),
        ):
            plan = _gpg_forwarding._gpg_forwarding()
        assert plan is not None
        self.assertFalse(plan.requires_sidecar)
        self.assertEqual(socket, plan.direct_socket)
        self.assertEqual(home, plan.credential_home)

    def test_direct_target_args_uses_the_direct_agent_socket(self) -> None:
        home = Path("/test-tmp/gnupg")
        socket = home / "S.gpg-agent"
        plan = _gpg_forwarding._GpgForwardingPlan(home, False, socket)
        expected = [BindMountSpec(Path("/test-tmp/client"), PurePosixPath("/client"))]
        with mock.patch.object(
            _gpg_forwarding,
            "_gpg_direct_target_args",
            return_value=nullcontext(expected),
        ) as target_args:
            with plan.direct_target_args() as actual:
                self.assertEqual(expected, actual)

        target_args.assert_called_once_with(socket, home)

    def test_prepare_direct_gpg_keys_uses_cached_keys_without_pinentry(self) -> None:
        home = Path("/test-tmp/gnupg")
        with (
            mock.patch.object(_gpg_forwarding, "_GPG", "/usr/bin/gpg"),
            mock.patch.object(
                _gpg_forwarding,
                "_resolve_host_gpg_secret_key_state",
                return_value=(["FIRST", "SECOND"], set()),
            ),
            mock.patch.object(
                _gpg_forwarding.subprocess,
                "run",
                return_value=mock.Mock(returncode=0),
            ) as run_mock,
        ):
            _gpg_forwarding._prepare_direct_gpg_keys(home, interactive=False)

        self.assertEqual(2, run_mock.call_count)
        for fingerprint, call in zip(
            ["FIRST", "SECOND"], run_mock.call_args_list, strict=True
        ):
            command = call.args[0]
            self.assertEqual("/usr/bin/gpg", command[0])
            self.assertEqual(["--batch", "--pinentry-mode", "error"], command[1:4])
            self.assertEqual(["--homedir", str(home)], command[4:6])
            self.assertIn(fingerprint, command)
            self.assertIn("--detach-sign", command)
            self.assertFalse(call.kwargs["check"])
            self.assertTrue(call.kwargs["capture_output"])

    def test_prepare_direct_gpg_keys_warns_for_uncached_noninteractive_key(
        self,
    ) -> None:
        home = Path("/test-tmp/gnupg")
        with (
            mock.patch.object(_gpg_forwarding, "_GPG", "/usr/bin/gpg"),
            mock.patch.object(
                _gpg_forwarding,
                "_resolve_host_gpg_secret_key_state",
                return_value=(["FINGERPRINT"], set()),
            ),
            mock.patch.object(
                _gpg_forwarding.subprocess, "run", return_value=mock.Mock(returncode=2)
            ) as run_mock,
        ):
            with self.assertLogs("aicage", "WARNING") as logs:
                _gpg_forwarding._prepare_direct_gpg_keys(home, interactive=False)

        run_mock.assert_called_once()
        self.assertIn("continuing without it", logs.output[0])

    def test_prepare_direct_gpg_keys_uses_host_gpg_interactively(self) -> None:
        home = Path("/test-tmp/gnupg")
        with (
            mock.patch.object(_gpg_forwarding, "_GPG", "/usr/bin/gpg"),
            mock.patch.object(
                _gpg_forwarding,
                "_resolve_host_gpg_secret_key_state",
                return_value=(["FINGERPRINT"], set()),
            ),
            mock.patch.object(
                _gpg_forwarding.subprocess,
                "run",
                side_effect=[mock.Mock(returncode=2), mock.Mock(returncode=0)],
            ) as run_mock,
        ):
            _gpg_forwarding._prepare_direct_gpg_keys(home, interactive=True)

        self.assertEqual(2, run_mock.call_count)
        self.assertNotIn("--batch", run_mock.call_args_list[1].args[0])

    def test_reload_gpg_keys_loads_unusable_keys_interactively(self) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        with (
            mock.patch.object(
                _gpg_forwarding,
                "_gpg_source_keygrips",
                return_value={"ONE"},
            ),
            mock.patch.object(
                _gpg_forwarding,
                "_gpg_fingerprints",
                return_value=["FIRST", "SECOND"],
            ),
            mock.patch.object(_gpg_forwarding, "_gpg_keygrips", return_value={"ONE"}),
            mock.patch.object(
                _gpg_forwarding,
                "_gpg_key_is_usable",
                side_effect=[False, True, False, True],
            ),
            mock.patch.object(
                _gpg_forwarding, "_load_gpg_key_interactively"
            ) as load_mock,
        ):
            _gpg_forwarding._reload_gpg_keys([resource], interactive=True)

        self.assertEqual(
            [
                mock.call(resource, "FIRST"),
                mock.call(resource, "SECOND"),
            ],
            load_mock.call_args_list,
        )

    def test_reload_gpg_keys_resets_stale_sidecar_state(self) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        with (
            mock.patch.object(
                _gpg_forwarding,
                "_gpg_source_keygrips",
                return_value={"HOST"},
            ),
            mock.patch.object(
                _gpg_forwarding,
                "_gpg_fingerprints",
                return_value=[],
            ),
            mock.patch.object(_gpg_forwarding, "_gpg_keygrips", return_value={"STALE"}),
            mock.patch.object(_gpg_forwarding, "_reset_gpg_agent") as reset_mock,
        ):
            _gpg_forwarding._reload_gpg_keys([resource], interactive=False)
        reset_mock.assert_called_once_with(resource)

    def test_reload_gpg_keys_warns_for_an_interactively_loaded_unusable_key(
        self,
    ) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        with (
            mock.patch.object(
                _gpg_forwarding,
                "_gpg_source_keygrips",
                return_value={"KEY"},
            ),
            mock.patch.object(
                _gpg_forwarding,
                "_gpg_fingerprints",
                return_value=["FINGERPRINT"],
            ),
            mock.patch.object(_gpg_forwarding, "_gpg_keygrips", return_value={"KEY"}),
            mock.patch.object(
                _gpg_forwarding, "_gpg_key_is_usable", side_effect=[False, False]
            ),
            mock.patch.object(_gpg_forwarding, "_load_gpg_key_interactively"),
            self.assertLogs("aicage", "WARNING") as logs,
        ):
            _gpg_forwarding._reload_gpg_keys([resource], interactive=True)
        self.assertIn("continuing without it", logs.output[0])

    def test_reload_gpg_keys_skips_cancelled_interactive_load(self) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        with (
            mock.patch.object(
                _gpg_forwarding,
                "_gpg_source_keygrips",
                return_value={"KEY"},
            ),
            mock.patch.object(
                _gpg_forwarding,
                "_gpg_fingerprints",
                return_value=["FINGERPRINT"],
            ),
            mock.patch.object(_gpg_forwarding, "_gpg_keygrips", return_value={"KEY"}),
            mock.patch.object(
                _gpg_forwarding, "_gpg_key_is_usable", return_value=False
            ),
            mock.patch.object(
                _gpg_forwarding,
                "_load_gpg_key_interactively",
                side_effect=DockerError("cancelled"),
            ),
            self.assertLogs("aicage", "WARNING") as logs,
        ):
            _gpg_forwarding._reload_gpg_keys([resource], interactive=True)
        self.assertIn("continuing without it", logs.output[0])

    def test_reload_gpg_keys_skips_usable_keys(self) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        with (
            mock.patch.object(
                _gpg_forwarding,
                "_gpg_source_keygrips",
                return_value={"KEY"},
            ),
            mock.patch.object(
                _gpg_forwarding,
                "_gpg_fingerprints",
                return_value=["FINGERPRINT"],
            ),
            mock.patch.object(_gpg_forwarding, "_gpg_keygrips", return_value={"KEY"}),
            mock.patch.object(_gpg_forwarding, "_gpg_key_is_usable", return_value=True),
            mock.patch.object(_gpg_forwarding, "_load_gpg_key_interactively"),
        ):
            _gpg_forwarding._reload_gpg_keys([resource], interactive=False)

    def test_reload_gpg_keys_warns_for_unusable_keys_noninteractively(self) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        with (
            mock.patch.object(
                _gpg_forwarding,
                "_gpg_source_keygrips",
                return_value={"KEY"},
            ),
            mock.patch.object(
                _gpg_forwarding,
                "_gpg_fingerprints",
                return_value=["FINGERPRINT"],
            ),
            mock.patch.object(_gpg_forwarding, "_gpg_keygrips", return_value={"KEY"}),
            mock.patch.object(
                _gpg_forwarding, "_gpg_key_is_usable", return_value=False
            ),
            self.assertLogs("aicage", "WARNING") as logs,
        ):
            _gpg_forwarding._reload_gpg_keys([resource], interactive=False)
        self.assertIn("continuing without it", logs.output[0])
