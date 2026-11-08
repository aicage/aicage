from contextlib import nullcontext
from pathlib import PurePosixPath
from unittest import TestCase, mock

from aicage.docker.errors import DockerError
from aicage.runtime.credential_agent import _resource_ssh
from aicage.runtime.credential_agent._resource_models import (
    _CredentialProtocol,
    _resources,
)


class ResourceSshTests(TestCase):
    def test_load_ssh_key_streams_passphrase_to_sidecar(self) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        stream = mock.Mock()
        client = mock.Mock()
        client.api.exec_create.return_value = {"Id": "exec-id"}
        client.api.exec_start.return_value = stream
        client.api.exec_inspect.return_value = {"ExitCode": 0}
        container = mock.Mock()
        with (
            mock.patch.object(_resource_ssh, "get_docker_client", return_value=client),
            mock.patch.object(_resource_ssh, "_find_container", return_value=container),
        ):
            _resource_ssh._load_ssh_key(
                resource, PurePosixPath("/credential/ssh/id_ed25519"), "secret"
            )

        stream.sendall.assert_called_once_with(b"secret\n")
        stream.close.assert_called_once()
        client.api.exec_create.assert_called_once_with(
            container.id,
            [
                "credential-agent",
                "ssh",
                "load",
                "/credential/ssh/id_ed25519",
                "/credential/ssh/id_ed25519",
            ],
            stdin=True,
            user=resource.user,
        )

    def test_load_ssh_key_rejects_missing_sidecar(self) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        with (
            mock.patch.object(_resource_ssh, "get_docker_client"),
            mock.patch.object(_resource_ssh, "_find_container", return_value=None),
            self.assertRaisesRegex(DockerError, "unavailable"),
        ):
            _resource_ssh._load_ssh_key(
                resource, PurePosixPath("/credential/ssh/id_ed25519"), ""
            )

    def test_load_ssh_key_interactively_attaches_the_terminal(self) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        stdin = mock.Mock()
        stdout = mock.Mock()
        result = mock.Mock(returncode=0)
        with (
            mock.patch.object(
                _resource_ssh,
                "terminal_streams",
                return_value=nullcontext((stdin, stdout)),
            ),
            mock.patch.object(
                _resource_ssh, "run_docker_command", return_value=result
            ) as run_mock,
        ):
            _resource_ssh._load_ssh_key_interactively(
                resource, PurePosixPath("/credential/ssh/id_ed25519")
            )

        run_mock.assert_called_once_with(
            [
                "docker",
                "exec",
                "--user",
                resource.user,
                "-it",
                resource.container_name,
                "credential-agent",
                "ssh",
                "load-interactive",
                "/credential/ssh/id_ed25519",
                "/credential/ssh/id_ed25519",
            ],
            check=False,
            stdin=stdin,
            stdout=stdout,
            stderr=stdout,
        )

    def test_list_ssh_identities_returns_sidecar_public_keys(self) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        client = mock.Mock()
        client.api.exec_create.return_value = {"Id": "list-id"}
        client.api.exec_start.return_value = b"ssh-ed25519 AAAA first\n"
        client.api.exec_inspect.return_value = {"ExitCode": 0}
        container = mock.Mock()
        with (
            mock.patch.object(_resource_ssh, "get_docker_client", return_value=client),
            mock.patch.object(_resource_ssh, "_find_container", return_value=container),
        ):
            identities = _resource_ssh._list_ssh_identities(resource)

        self.assertEqual(["ssh-ed25519 AAAA first"], identities)
        client.api.exec_create.assert_called_once_with(
            container.id,
            ["credential-agent", "ssh", "list"],
            user=resource.user,
        )

    def test_ssh_key_fingerprint_reads_the_sidecar_result(self) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        client = mock.Mock()
        client.api.exec_create.return_value = {"Id": "fingerprint"}
        client.api.exec_start.return_value = b"SHA256:key\n"
        client.api.exec_inspect.return_value = {"ExitCode": 0}
        container = mock.Mock()
        with (
            mock.patch.object(_resource_ssh, "get_docker_client", return_value=client),
            mock.patch.object(_resource_ssh, "_find_container", return_value=container),
        ):
            fingerprint = _resource_ssh._ssh_key_fingerprint(
                resource, PurePosixPath("/credential/ssh/id_ed25519")
            )

        self.assertEqual("SHA256:key", fingerprint)
        client.api.exec_create.assert_called_once_with(
            container.id,
            [
                "credential-agent",
                "ssh",
                "fingerprint",
                "/credential/ssh/id_ed25519",
            ],
            user=resource.user,
        )

    def test_ssh_key_is_encrypted_reads_the_sidecar_result(self) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        client = mock.Mock()
        client.api.exec_create.return_value = {"Id": "encrypted"}
        client.api.exec_start.return_value = b"encrypted\n"
        client.api.exec_inspect.return_value = {"ExitCode": 0}
        with (
            mock.patch.object(_resource_ssh, "get_docker_client", return_value=client),
            mock.patch.object(
                _resource_ssh, "_find_container", return_value=mock.Mock()
            ),
        ):
            self.assertTrue(
                _resource_ssh._ssh_key_is_encrypted(
                    resource, PurePosixPath("/credential/ssh/id_ed25519")
                )
            )

    def test_remove_ssh_identity_streams_public_key_to_sidecar(self) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        client = mock.Mock()
        stream = mock.Mock()
        client.api.exec_create.return_value = {"Id": "remove-id"}
        client.api.exec_start.return_value = stream
        client.api.exec_inspect.return_value = {"ExitCode": 0}
        container = mock.Mock()
        with (
            mock.patch.object(_resource_ssh, "get_docker_client", return_value=client),
            mock.patch.object(_resource_ssh, "_find_container", return_value=container),
        ):
            _resource_ssh._remove_ssh_identity(resource, "ssh-ed25519 AAAA key")

        stream.sendall.assert_called_once_with(b"ssh-ed25519 AAAA key\n")
        client.api.exec_create.assert_called_once_with(
            container.id,
            ["credential-agent", "ssh", "remove"],
            stdin=True,
            user=resource.user,
        )

    def test_load_ssh_key_rejects_a_failed_exec(self) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        client = mock.Mock()
        client.api.exec_create.return_value = {"Id": "exec-id"}
        stream = mock.Mock()
        client.api.exec_start.return_value = stream
        client.api.exec_inspect.return_value = {"ExitCode": 1}
        with (
            mock.patch.object(_resource_ssh, "get_docker_client", return_value=client),
            mock.patch.object(
                _resource_ssh, "_find_container", return_value=mock.Mock()
            ),
            self.assertRaisesRegex(DockerError, "Failed to load"),
        ):
            _resource_ssh._load_ssh_key(
                resource, PurePosixPath("/credential/ssh/id_ed25519"), ""
            )

    def test_load_ssh_key_waits_for_remote_exec_completion(self) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        stream = mock.Mock()
        client = mock.Mock()
        client.api.exec_create.return_value = {"Id": "exec-id"}
        client.api.exec_start.return_value = stream
        client.api.exec_inspect.side_effect = [
            {"Running": True, "ExitCode": None},
            {"Running": False, "ExitCode": 0},
        ]
        with (
            mock.patch.object(_resource_ssh, "get_docker_client", return_value=client),
            mock.patch.object(
                _resource_ssh, "_find_container", return_value=mock.Mock()
            ),
            mock.patch("aicage.runtime.credential_agent._resource_exec.time.sleep"),
        ):
            _resource_ssh._load_ssh_key(
                resource, PurePosixPath("/credential/ssh/id_ed25519"), ""
            )

        self.assertEqual(2, client.api.exec_inspect.call_count)

    def test_load_ssh_key_does_not_read_exec_output(self) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        stream = mock.Mock()
        client = mock.Mock()
        client.api.exec_create.return_value = {"Id": "load-id"}
        client.api.exec_start.return_value = stream
        client.api.exec_inspect.return_value = {"ExitCode": 1}
        with (
            mock.patch.object(_resource_ssh, "get_docker_client", return_value=client),
            mock.patch.object(
                _resource_ssh, "_find_container", return_value=mock.Mock()
            ),
            self.assertRaisesRegex(DockerError, "Failed to load"),
        ):
            _resource_ssh._load_ssh_key(
                resource, PurePosixPath("/credential/ssh/id_ed25519"), ""
            )

        stream.recv.assert_not_called()

    def test_load_ssh_key_translates_docker_exec_errors(self) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        client = mock.Mock()
        client.api.exec_create.side_effect = _resource_ssh.DockerException("failed")
        with (
            mock.patch.object(_resource_ssh, "get_docker_client", return_value=client),
            mock.patch.object(
                _resource_ssh, "_find_container", return_value=mock.Mock()
            ),
            self.assertRaisesRegex(DockerError, "Failed to load"),
        ):
            _resource_ssh._load_ssh_key(
                resource, PurePosixPath("/credential/ssh/id_ed25519"), ""
            )
