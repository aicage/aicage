import subprocess
from pathlib import Path, PurePosixPath
from unittest import TestCase, mock

from aicage.docker.errors import DockerError
from aicage.runtime.credential_agent import _ssh_forwarding
from aicage.runtime.credential_agent._resource_models import (
    _CredentialProtocol,
    _resources,
)
from aicage.runtime.run_args import BindMountSpec, EnvVar, MountSpec, VolumeMountSpec


class SshForwardingTests(TestCase):
    def test_ssh_forwarding_skips_sidecar_without_keys_or_ssh_home(self) -> None:
        with (
            mock.patch.object(_ssh_forwarding, "_direct_ssh_socket", return_value=None),
            mock.patch.object(
                _ssh_forwarding, "_resolve_ssh_key_files", return_value=[]
            ),
            mock.patch.object(
                _ssh_forwarding, "_resolve_ssh_support_files", return_value=[]
            ),
            mock.patch.object(Path, "is_dir", return_value=False),
        ):
            self.assertEqual(
                _ssh_forwarding._SshForwardingPlan([], [], False, None),
                _ssh_forwarding._ssh_forwarding(),
            )

    def test_ssh_forwarding_uses_a_sidecar_for_ssh_keys_or_home(self) -> None:
        with (
            mock.patch.object(_ssh_forwarding, "_direct_ssh_socket", return_value=None),
            mock.patch.object(
                _ssh_forwarding,
                "_resolve_ssh_key_files",
                return_value=[Path("/test-tmp/id_ed25519")],
            ),
            mock.patch.object(
                _ssh_forwarding, "_resolve_ssh_support_files", return_value=[]
            ),
        ):
            self.assertEqual(
                _ssh_forwarding._SshForwardingPlan([], [], True, None),
                _ssh_forwarding._ssh_forwarding(),
            )

    def test_ssh_forwarding_uses_direct_host_agent(self) -> None:
        socket = Path("/test-tmp/ssh-agent.sock")
        public_key = Path("/test-tmp/id_ed25519.pub")
        direct_mount = BindMountSpec(
            socket, PurePosixPath("/run/credential-agent/ssh-agent.sock")
        )
        direct_env = EnvVar("SSH_AUTH_SOCK", "/run/credential-agent/ssh-agent.sock")
        with (
            mock.patch.object(
                _ssh_forwarding,
                "_direct_ssh_socket",
                return_value=socket,
            ),
            mock.patch.object(
                _ssh_forwarding,
                "_resolve_ssh_support_files",
                return_value=[public_key],
            ),
        ):
            plan = _ssh_forwarding._ssh_forwarding()

        self.assertEqual(
            [
                direct_mount,
                BindMountSpec(
                    public_key, PurePosixPath("/test-tmp/id_ed25519.pub"), True
                ),
            ],
            plan.mounts,
        )
        self.assertEqual([direct_env], plan.env)
        self.assertFalse(plan.requires_sidecar)
        self.assertEqual(socket, plan.direct_socket)

    def test_direct_ssh_socket_requires_a_reachable_non_windows_unix_socket(
        self,
    ) -> None:
        with (
            mock.patch.object(_ssh_forwarding.os, "name", "posix"),
            mock.patch.object(_ssh_forwarding, "_SSH_ADD", "/usr/bin/ssh-add"),
            mock.patch.object(Path, "is_socket", return_value=True),
            mock.patch.object(
                _ssh_forwarding.subprocess,
                "run",
                return_value=mock.Mock(returncode=1),
            ) as run_mock,
        ):
            socket = Path("/test-tmp/ssh-agent.sock")
            with mock.patch.dict(
                _ssh_forwarding.os.environ, {"SSH_AUTH_SOCK": str(socket)}
            ):
                self.assertEqual(socket, _ssh_forwarding._direct_ssh_socket())

        run_mock.assert_called_once_with(
            ["/usr/bin/ssh-add", "-l"],
            env=mock.ANY,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_direct_ssh_socket_rejects_windows_or_unreachable_agents(self) -> None:
        with mock.patch.object(_ssh_forwarding.os, "name", "nt"):
            self.assertIsNone(_ssh_forwarding._direct_ssh_socket())

        socket = Path("/test-tmp/ssh-agent.sock")
        with (
            mock.patch.object(_ssh_forwarding.os, "name", "posix"),
            mock.patch.object(_ssh_forwarding, "_SSH_ADD", "/usr/bin/ssh-add"),
            mock.patch.dict(_ssh_forwarding.os.environ, {"SSH_AUTH_SOCK": str(socket)}),
            mock.patch.object(Path, "is_socket", return_value=True),
            mock.patch.object(
                _ssh_forwarding.subprocess,
                "run",
                return_value=mock.Mock(returncode=2),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Cannot communicate"):
                _ssh_forwarding._direct_ssh_socket()

    def test_direct_ssh_socket_uses_the_sidecar_without_host_keygen(self) -> None:
        with (
            mock.patch.object(_ssh_forwarding.os, "name", "posix"),
            mock.patch.object(_ssh_forwarding, "_SSH_ADD", "/usr/bin/ssh-add"),
            mock.patch.object(_ssh_forwarding, "_SSH_KEYGEN", None),
            mock.patch.object(_ssh_forwarding.subprocess, "run") as run_mock,
        ):
            self.assertIsNone(_ssh_forwarding._direct_ssh_socket())

        run_mock.assert_not_called()

    def test_prepare_host_ssh_agent_loads_missing_unprotected_key(self) -> None:
        socket = Path("/test-tmp/ssh-agent.sock")
        key = Path("/test-tmp/.ssh/id_ed25519")
        with (
            mock.patch.object(_ssh_forwarding, "_host_ssh_identities", return_value=[]),
            mock.patch.object(
                _ssh_forwarding, "_resolve_ssh_key_files", return_value=[key]
            ),
            mock.patch.object(
                _ssh_forwarding, "_ssh_key_fingerprint", return_value="SHA256:key"
            ),
            mock.patch.object(
                _ssh_forwarding, "_ssh_key_is_encrypted", return_value=False
            ),
            mock.patch.object(
                _ssh_forwarding, "_load_host_ssh_key", return_value=True
            ) as load_mock,
        ):
            _ssh_forwarding._prepare_host_ssh_agent(socket, interactive=False)

        load_mock.assert_called_once_with(socket, key, interactive=False)

    def test_prepare_host_ssh_agent_skips_loaded_key(self) -> None:
        socket = Path("/test-tmp/ssh-agent.sock")
        key = Path("/test-tmp/.ssh/id_ed25519")
        with (
            mock.patch.object(
                _ssh_forwarding,
                "_host_ssh_identities",
                return_value=["ssh-ed25519 AAAA key"],
            ),
            mock.patch.object(
                _ssh_forwarding, "_resolve_ssh_key_files", return_value=[key]
            ),
            mock.patch.object(
                _ssh_forwarding,
                "_ssh_identity_fingerprint",
                return_value="SHA256:key",
            ),
            mock.patch.object(
                _ssh_forwarding, "_ssh_key_fingerprint", return_value="SHA256:key"
            ),
            mock.patch.object(_ssh_forwarding, "_load_host_ssh_key") as load_mock,
        ):
            _ssh_forwarding._prepare_host_ssh_agent(socket, interactive=False)

        load_mock.assert_not_called()

    def test_prepare_host_ssh_agent_skips_missing_protected_key_noninteractively(
        self,
    ) -> None:
        key = Path("/test-tmp/.ssh/id_ed25519")
        with (
            mock.patch.object(_ssh_forwarding, "_host_ssh_identities", return_value=[]),
            mock.patch.object(
                _ssh_forwarding, "_resolve_ssh_key_files", return_value=[key]
            ),
            mock.patch.object(
                _ssh_forwarding, "_ssh_key_fingerprint", return_value="SHA256:key"
            ),
            mock.patch.object(
                _ssh_forwarding, "_ssh_key_is_encrypted", return_value=True
            ),
            self.assertLogs("aicage", "WARNING") as logs,
        ):
            _ssh_forwarding._prepare_host_ssh_agent(
                Path("/test-tmp/ssh-agent.sock"), interactive=False
            )
        self.assertIn("continuing without it", logs.output[0])

    def test_prepare_host_ssh_agent_loads_missing_protected_key_interactively(
        self,
    ) -> None:
        socket = Path("/test-tmp/ssh-agent.sock")
        key = Path("/test-tmp/.ssh/id_ed25519")
        with (
            mock.patch.object(_ssh_forwarding, "_host_ssh_identities", return_value=[]),
            mock.patch.object(
                _ssh_forwarding, "_resolve_ssh_key_files", return_value=[key]
            ),
            mock.patch.object(
                _ssh_forwarding, "_ssh_key_fingerprint", return_value="SHA256:key"
            ),
            mock.patch.object(
                _ssh_forwarding, "_ssh_key_is_encrypted", return_value=True
            ),
            mock.patch.object(
                _ssh_forwarding, "_load_host_ssh_key", return_value=True
            ) as load_mock,
        ):
            _ssh_forwarding._prepare_host_ssh_agent(socket, interactive=True)

        load_mock.assert_called_once_with(socket, key, interactive=True)

    def test_prepare_host_ssh_agent_skips_cancelled_protected_key(self) -> None:
        socket = Path("/test-tmp/ssh-agent.sock")
        key = Path("/test-tmp/.ssh/id_ed25519")
        with (
            mock.patch.object(_ssh_forwarding, "_host_ssh_identities", return_value=[]),
            mock.patch.object(
                _ssh_forwarding, "_resolve_ssh_key_files", return_value=[key]
            ),
            mock.patch.object(
                _ssh_forwarding, "_ssh_key_fingerprint", return_value="SHA256:key"
            ),
            mock.patch.object(
                _ssh_forwarding, "_ssh_key_is_encrypted", return_value=True
            ),
            mock.patch.object(
                _ssh_forwarding, "_load_host_ssh_key", return_value=False
            ) as load_mock,
            self.assertLogs("aicage", "WARNING") as logs,
        ):
            _ssh_forwarding._prepare_host_ssh_agent(socket, interactive=True)

        load_mock.assert_called_once_with(socket, key, interactive=True)
        self.assertIn("continuing without it", logs.output[0])

    def test_prepare_ssh_forwarding_prepares_a_direct_host_agent(self) -> None:
        socket = Path("/test-tmp/ssh-agent.sock")
        plan = _ssh_forwarding._SshForwardingPlan([], [], False, socket)
        with mock.patch.object(
            _ssh_forwarding, "_prepare_host_ssh_agent"
        ) as prepare_mock:
            _ssh_forwarding._prepare_ssh_forwarding(plan, interactive=False)

        prepare_mock.assert_called_once_with(socket, interactive=False)

    def test_prepare_ssh_forwarding_skips_a_sidecar_plan(self) -> None:
        plan = _ssh_forwarding._SshForwardingPlan([], [], True, None)
        with mock.patch.object(
            _ssh_forwarding, "_prepare_host_ssh_agent"
        ) as prepare_mock:
            _ssh_forwarding._prepare_ssh_forwarding(plan, interactive=False)

        prepare_mock.assert_not_called()

    def test_direct_ssh_socket_rejects_missing_or_non_socket_paths(self) -> None:
        with (
            mock.patch.object(_ssh_forwarding.os, "name", "posix"),
            mock.patch.object(_ssh_forwarding, "_SSH_ADD", "/usr/bin/ssh-add"),
            mock.patch.dict(_ssh_forwarding.os.environ, {}, clear=True),
        ):
            self.assertIsNone(_ssh_forwarding._direct_ssh_socket())

        with (
            mock.patch.object(_ssh_forwarding.os, "name", "posix"),
            mock.patch.object(_ssh_forwarding, "_SSH_ADD", "/usr/bin/ssh-add"),
            mock.patch.dict(
                _ssh_forwarding.os.environ,
                {"SSH_AUTH_SOCK": "/test-tmp/not-a-socket"},
                clear=True,
            ),
            mock.patch.object(Path, "is_socket", return_value=False),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "does not refer to a Unix socket"
            ):
                _ssh_forwarding._direct_ssh_socket()

    def test_host_ssh_identities_handles_agent_results(self) -> None:
        socket = Path("/test-tmp/ssh-agent.sock")
        with mock.patch.object(_ssh_forwarding, "_SSH_ADD", None):
            self.assertIsNone(_ssh_forwarding._host_ssh_identities(socket))

        with (
            mock.patch.object(_ssh_forwarding, "_SSH_ADD", "/usr/bin/ssh-add"),
            mock.patch.object(
                _ssh_forwarding.subprocess,
                "run",
                side_effect=[
                    mock.Mock(returncode=1, stdout=""),
                    mock.Mock(
                        returncode=0, stdout="ssh-ed25519 AAAA one\nssh-rsa BBBB two\n"
                    ),
                    mock.Mock(returncode=2, stdout=""),
                ],
            ),
        ):
            self.assertEqual([], _ssh_forwarding._host_ssh_identities(socket))
            self.assertEqual(
                ["ssh-ed25519 AAAA one", "ssh-rsa BBBB two"],
                _ssh_forwarding._host_ssh_identities(socket),
            )
            self.assertIsNone(_ssh_forwarding._host_ssh_identities(socket))

    def test_prepare_host_ssh_agent_rejects_identity_or_unprotected_load_failure(
        self,
    ) -> None:
        socket = Path("/test-tmp/ssh-agent.sock")
        key = Path("/test-tmp/.ssh/id_ed25519")
        with mock.patch.object(
            _ssh_forwarding, "_host_ssh_identities", return_value=None
        ):
            with self.assertRaisesRegex(RuntimeError, "Cannot list identities"):
                _ssh_forwarding._prepare_host_ssh_agent(socket, interactive=False)

        with (
            mock.patch.object(_ssh_forwarding, "_host_ssh_identities", return_value=[]),
            mock.patch.object(
                _ssh_forwarding, "_resolve_ssh_key_files", return_value=[key]
            ),
            mock.patch.object(
                _ssh_forwarding, "_ssh_key_fingerprint", return_value="SHA256:key"
            ),
            mock.patch.object(
                _ssh_forwarding, "_ssh_key_is_encrypted", return_value=False
            ),
            mock.patch.object(
                _ssh_forwarding, "_load_host_ssh_key", return_value=False
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Failed to load unprotected"):
                _ssh_forwarding._prepare_host_ssh_agent(socket, interactive=False)

    def test_load_host_ssh_key_uses_interactive_and_noninteractive_modes(
        self,
    ) -> None:
        socket = Path("/test-tmp/ssh-agent.sock")
        key = Path("/test-tmp/.ssh/id_ed25519")
        with (
            mock.patch.object(_ssh_forwarding, "_SSH_ADD", "/usr/bin/ssh-add"),
            mock.patch.object(
                _ssh_forwarding.subprocess,
                "run",
                side_effect=[mock.Mock(returncode=0), mock.Mock(returncode=1)],
            ) as run_mock,
        ):
            self.assertTrue(
                _ssh_forwarding._load_host_ssh_key(socket, key, interactive=True)
            )
            self.assertFalse(
                _ssh_forwarding._load_host_ssh_key(socket, key, interactive=False)
            )

        self.assertEqual(
            ["/usr/bin/ssh-add", str(key)],
            run_mock.call_args_list[0].args[0],
        )
        self.assertEqual(subprocess.DEVNULL, run_mock.call_args_list[1].kwargs["stdin"])

    def test_load_host_ssh_key_rejects_a_missing_host_tool(self) -> None:
        with mock.patch.object(_ssh_forwarding, "_SSH_ADD", None):
            self.assertFalse(
                _ssh_forwarding._load_host_ssh_key(
                    Path("/test-tmp/ssh-agent.sock"),
                    Path("/test-tmp/.ssh/id_ed25519"),
                    interactive=False,
                )
            )

    def test_ssh_key_is_encrypted_interprets_host_keygen_result(self) -> None:
        key = Path("/test-tmp/.ssh/id_ed25519")
        with (
            mock.patch.object(
                _ssh_forwarding, "_ssh_keygen", return_value="/usr/bin/ssh-keygen"
            ),
            mock.patch.object(
                _ssh_forwarding.subprocess,
                "run",
                side_effect=[mock.Mock(returncode=0), mock.Mock(returncode=1)],
            ),
        ):
            self.assertFalse(_ssh_forwarding._ssh_key_is_encrypted(key))
            self.assertTrue(_ssh_forwarding._ssh_key_is_encrypted(key))

    def test_append_ssh_target_args_adds_socket_volume_and_environment(self) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        mounts: list[MountSpec] = []
        env: list[EnvVar] = []
        _ssh_forwarding._append_ssh_target_args(resource, mounts, env)
        self.assertEqual(
            [
                VolumeMountSpec(
                    resource.volume_name,
                    PurePosixPath("/run/credential-agent"),
                    True,
                )
            ],
            mounts,
        )
        self.assertEqual(
            [EnvVar("SSH_AUTH_SOCK", "/run/credential-agent/ssh-agent.sock")],
            env,
        )

    def test_reload_ssh_keys_loads_missing_key_with_an_empty_passphrase(
        self,
    ) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        key = Path("/test-tmp/.ssh/id_ed25519")
        with (
            mock.patch.object(_ssh_forwarding, "HOST_SSH_DIR", key.parent),
            mock.patch.object(
                _ssh_forwarding, "_resolve_ssh_key_files", return_value=[key]
            ),
            mock.patch.object(
                _ssh_forwarding,
                "_sidecar_ssh_key_fingerprint",
                return_value="SHA256:key",
            ),
            mock.patch.object(_ssh_forwarding, "_list_ssh_identities", return_value=[]),
            mock.patch.object(_ssh_forwarding, "_load_ssh_key") as load_mock,
        ):
            _ssh_forwarding._reload_ssh_keys([resource], interactive=False)
        load_mock.assert_called_once_with(
            resource,
            resource.credential_directory / "id_ed25519",
            "",
            PurePosixPath("/test-tmp/.ssh/id_ed25519"),
        )

    def test_reload_ssh_keys_prompts_only_after_empty_passphrase_load_fails(
        self,
    ) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        key = Path("/test-tmp/.ssh/id_ed25519")
        with (
            mock.patch.object(_ssh_forwarding, "HOST_SSH_DIR", key.parent),
            mock.patch.object(
                _ssh_forwarding, "_resolve_ssh_key_files", return_value=[key]
            ),
            mock.patch.object(
                _ssh_forwarding,
                "_sidecar_ssh_key_fingerprint",
                return_value="SHA256:key",
            ),
            mock.patch.object(_ssh_forwarding, "_list_ssh_identities", return_value=[]),
            mock.patch.object(
                _ssh_forwarding,
                "_load_ssh_key",
                side_effect=DockerError("passphrase required"),
            ),
            mock.patch.object(
                _ssh_forwarding, "_sidecar_ssh_key_is_encrypted", return_value=True
            ),
            mock.patch.object(
                _ssh_forwarding, "_load_ssh_key_interactively"
            ) as prompt_mock,
        ):
            _ssh_forwarding._reload_ssh_keys([resource], interactive=True)

        prompt_mock.assert_called_once_with(
            resource,
            resource.credential_directory / "id_ed25519",
            PurePosixPath("/test-tmp/.ssh/id_ed25519"),
        )

    def test_reload_ssh_keys_skips_unavailable_protected_key_noninteractively(
        self,
    ) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        key = Path("/test-tmp/.ssh/id_ed25519")
        with (
            mock.patch.object(_ssh_forwarding, "HOST_SSH_DIR", key.parent),
            mock.patch.object(
                _ssh_forwarding, "_resolve_ssh_key_files", return_value=[key]
            ),
            mock.patch.object(
                _ssh_forwarding,
                "_sidecar_ssh_key_fingerprint",
                return_value="SHA256:key",
            ),
            mock.patch.object(_ssh_forwarding, "_list_ssh_identities", return_value=[]),
            mock.patch.object(
                _ssh_forwarding,
                "_load_ssh_key",
                side_effect=DockerError("passphrase required"),
            ),
            mock.patch.object(
                _ssh_forwarding, "_sidecar_ssh_key_is_encrypted", return_value=True
            ),
            mock.patch.object(
                _ssh_forwarding, "_load_ssh_key_interactively"
            ) as prompt_mock,
            self.assertLogs("aicage", "WARNING") as logs,
        ):
            _ssh_forwarding._reload_ssh_keys([resource], interactive=False)

        prompt_mock.assert_not_called()
        self.assertIn("continuing without it", logs.output[0])

    def test_reload_ssh_keys_skips_cancelled_protected_key(self) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        key = Path("/test-tmp/.ssh/id_ed25519")
        with (
            mock.patch.object(_ssh_forwarding, "HOST_SSH_DIR", key.parent),
            mock.patch.object(
                _ssh_forwarding, "_resolve_ssh_key_files", return_value=[key]
            ),
            mock.patch.object(
                _ssh_forwarding,
                "_sidecar_ssh_key_fingerprint",
                return_value="SHA256:key",
            ),
            mock.patch.object(_ssh_forwarding, "_list_ssh_identities", return_value=[]),
            mock.patch.object(
                _ssh_forwarding,
                "_load_ssh_key",
                side_effect=DockerError("passphrase required"),
            ),
            mock.patch.object(
                _ssh_forwarding, "_sidecar_ssh_key_is_encrypted", return_value=True
            ),
            mock.patch.object(
                _ssh_forwarding,
                "_load_ssh_key_interactively",
                side_effect=DockerError("cancelled"),
            ),
            self.assertLogs("aicage", "WARNING") as logs,
        ):
            _ssh_forwarding._reload_ssh_keys([resource], interactive=True)

        self.assertIn("continuing without it", logs.output[0])

    def test_reload_ssh_keys_removes_stale_and_keeps_loaded_identities(self) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        key = Path("/test-tmp/.ssh/id_ed25519")
        current_identity = "ssh-ed25519 AAAA current"
        stale_identity = "ssh-ed25519 AAAA stale"
        with (
            mock.patch.object(_ssh_forwarding, "HOST_SSH_DIR", key.parent),
            mock.patch.object(
                _ssh_forwarding, "_resolve_ssh_key_files", return_value=[key]
            ),
            mock.patch.object(
                _ssh_forwarding,
                "_sidecar_ssh_key_fingerprint",
                return_value="SHA256:current",
            ),
            mock.patch.object(
                _ssh_forwarding,
                "_list_ssh_identities",
                return_value=[current_identity, stale_identity],
            ),
            mock.patch.object(
                _ssh_forwarding,
                "_sidecar_ssh_identity_fingerprint",
                side_effect=["SHA256:current", "SHA256:stale"],
            ),
            mock.patch.object(_ssh_forwarding, "_remove_ssh_identity") as remove_mock,
            mock.patch.object(_ssh_forwarding, "_load_ssh_key") as load_mock,
        ):
            _ssh_forwarding._reload_ssh_keys([resource], interactive=False)

        remove_mock.assert_called_once_with(resource, stale_identity)
        load_mock.assert_not_called()

    def test_reload_ssh_keys_skips_missing_and_rejects_external_resources(self) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        _ssh_forwarding._reload_ssh_keys([resource], interactive=False)

        ssh_resource = _resources([_CredentialProtocol.SSH])[0]
        with (
            mock.patch.object(
                _ssh_forwarding,
                "_resolve_ssh_key_files",
                return_value=[Path("/outside/key")],
            ),
            mock.patch.object(_ssh_forwarding, "HOST_SSH_DIR", Path("/test-tmp/.ssh")),
            self.assertRaisesRegex(RuntimeError, "outside"),
        ):
            _ssh_forwarding._reload_ssh_keys([ssh_resource], interactive=False)

    def test_ssh_key_fingerprint_interprets_command_results(self) -> None:
        key = Path("/test-tmp/id_ed25519")
        with (
            mock.patch.object(
                _ssh_forwarding, "_ssh_keygen", return_value="/usr/bin/ssh-keygen"
            ),
            mock.patch.object(
                _ssh_forwarding.subprocess,
                "run",
                return_value=mock.Mock(returncode=0, stdout="256 SHA256:key comment"),
            ),
            mock.patch.object(Path, "is_file", return_value=False),
        ):
            self.assertEqual("SHA256:key", _ssh_forwarding._ssh_key_fingerprint(key))

    def test_ssh_identity_fingerprint_interprets_sidecar_public_key(self) -> None:
        with (
            mock.patch.object(
                _ssh_forwarding, "_ssh_keygen", return_value="/usr/bin/ssh-keygen"
            ),
            mock.patch.object(
                _ssh_forwarding.subprocess,
                "run",
                return_value=mock.Mock(returncode=0, stdout="256 SHA256:key comment"),
            ) as run_mock,
        ):
            fingerprint = _ssh_forwarding._ssh_identity_fingerprint(
                "ssh-ed25519 AAAA key"
            )

        self.assertEqual("SHA256:key", fingerprint)
        run_mock.assert_called_once_with(
            ["/usr/bin/ssh-keygen", "-lf", "-", "-E", "sha256"],
            input="ssh-ed25519 AAAA key\n",
            check=False,
            capture_output=True,
            text=True,
        )

    def test_ssh_keygen_requires_the_host_tool(self) -> None:
        with (
            mock.patch.object(_ssh_forwarding, "_SSH_KEYGEN", None),
            self.assertRaisesRegex(RuntimeError, "ssh-keygen is required"),
        ):
            _ssh_forwarding._ssh_keygen()

    def test_ssh_keygen_returns_the_absolute_host_tool_path(self) -> None:
        with mock.patch.object(_ssh_forwarding, "_SSH_KEYGEN", "/usr/bin/ssh-keygen"):
            self.assertEqual("/usr/bin/ssh-keygen", _ssh_forwarding._ssh_keygen())

    def test_ssh_key_fingerprint_rejects_invalid_command_output(self) -> None:
        key = Path("/test-tmp/id_ed25519")
        with (
            mock.patch.object(
                _ssh_forwarding, "_ssh_keygen", return_value="/usr/bin/ssh-keygen"
            ),
            mock.patch.object(
                _ssh_forwarding.subprocess,
                "run",
                return_value=mock.Mock(returncode=1, stdout=""),
            ),
            self.assertRaisesRegex(RuntimeError, "Cannot determine the fingerprint"),
        ):
            _ssh_forwarding._ssh_key_fingerprint(key)
