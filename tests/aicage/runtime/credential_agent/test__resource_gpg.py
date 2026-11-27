from unittest import TestCase, mock

from aicage.docker.errors import DockerError
from aicage.runtime.credential_agent import _resource_gpg
from aicage.runtime.credential_agent._resource_models import (
    _CredentialProtocol,
    _resources,
)


class ResourceGpgTests(TestCase):
    def test_gpg_key_is_usable_reads_the_sidecar_result(self) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        client = mock.Mock()
        client.api.exec_create.return_value = {"Id": "usable"}
        client.api.exec_start.return_value = b"usable\n"
        client.api.exec_inspect.return_value = {"ExitCode": 0}
        container = mock.Mock()
        with (
            mock.patch.object(_resource_gpg, "get_docker_client", return_value=client),
            mock.patch.object(_resource_gpg, "_find_container", return_value=container),
        ):
            self.assertTrue(_resource_gpg._gpg_key_is_usable(resource, "FINGERPRINT"))

        client.api.exec_create.assert_called_once_with(
            container.id,
            ["credential-agent", "gpg", "usable", "FINGERPRINT"],
            user=resource.user,
        )

    def test_gpg_key_is_usable_rejects_a_failed_exec(self) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        client = mock.Mock()
        client.api.exec_create.return_value = {"Id": "exec-id"}
        client.api.exec_start.return_value = b"gpg: key lookup failed\n"
        client.api.exec_inspect.return_value = {"ExitCode": 1}
        with (
            mock.patch.object(_resource_gpg, "get_docker_client", return_value=client),
            mock.patch.object(
                _resource_gpg, "_find_container", return_value=mock.Mock()
            ),
            self.assertRaisesRegex(DockerError, "gpg: key lookup failed"),
        ):
            _resource_gpg._gpg_key_is_usable(resource, "FINGERPRINT")

    def test_gpg_key_is_usable_rejects_an_unexpected_sidecar_result(self) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        client = mock.Mock()
        client.api.exec_create.return_value = {"Id": "usable"}
        client.api.exec_start.return_value = b"unknown\n"
        client.api.exec_inspect.return_value = {"ExitCode": 0}
        with (
            mock.patch.object(_resource_gpg, "get_docker_client", return_value=client),
            mock.patch.object(
                _resource_gpg, "_find_container", return_value=mock.Mock()
            ),
            self.assertRaisesRegex(DockerError, "Unexpected GnuPG usability result"),
        ):
            _resource_gpg._gpg_key_is_usable(resource, "FINGERPRINT")

    def test_gpg_keygrips_returns_the_sidecar_state(self) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        client = mock.Mock()
        client.api.exec_create.return_value = {"Id": "keygrips"}
        client.api.exec_start.return_value = b"FIRST\nSECOND\n"
        client.api.exec_inspect.return_value = {"ExitCode": 0}
        with (
            mock.patch.object(_resource_gpg, "get_docker_client", return_value=client),
            mock.patch.object(
                _resource_gpg, "_find_container", return_value=mock.Mock()
            ),
        ):
            self.assertEqual({"FIRST", "SECOND"}, _resource_gpg._gpg_keygrips(resource))

    def test_gpg_metadata_reads_active_and_source_sidecar_state(self) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        client = mock.Mock()
        client.api.exec_create.side_effect = [
            {"Id": "fingerprints"},
            {"Id": "keygrips"},
        ]
        client.api.exec_start.side_effect = [b"FIRST\nSECOND\n", b"ONE\nTWO\n"]
        client.api.exec_inspect.return_value = {"ExitCode": 0}
        with (
            mock.patch.object(_resource_gpg, "get_docker_client", return_value=client),
            mock.patch.object(
                _resource_gpg, "_find_container", return_value=mock.Mock()
            ),
        ):
            self.assertEqual(
                ["FIRST", "SECOND"], _resource_gpg._gpg_fingerprints(resource)
            )
            self.assertEqual(
                {"ONE", "TWO"}, _resource_gpg._gpg_source_keygrips(resource)
            )

    def test_reset_gpg_agent_runs_the_sidecar_reset_command(self) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        client = mock.Mock()
        client.api.exec_create.return_value = {"Id": "reset"}
        client.api.exec_start.return_value = b""
        client.api.exec_inspect.return_value = {"ExitCode": 0}
        container = mock.Mock()
        with (
            mock.patch.object(_resource_gpg, "get_docker_client", return_value=client),
            mock.patch.object(_resource_gpg, "_find_container", return_value=container),
        ):
            _resource_gpg._reset_gpg_agent(resource)

        client.api.exec_create.assert_called_once_with(
            container.id,
            ["credential-agent", "gpg", "reset"],
            user=resource.user,
        )

    def test_load_gpg_key_interactively_attaches_to_the_terminal(self) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        streams = mock.MagicMock()
        streams.__enter__.return_value = (mock.Mock(), mock.Mock())
        with (
            mock.patch.object(_resource_gpg, "terminal_streams", return_value=streams),
            mock.patch.object(
                _resource_gpg,
                "run_docker_command",
                return_value=mock.Mock(returncode=0),
            ) as run_mock,
        ):
            _resource_gpg._load_gpg_key_interactively(resource, "FINGERPRINT")

        run_mock.assert_called_once_with(
            [
                "docker",
                "exec",
                "--user",
                resource.user,
                "-it",
                resource.container_name,
                "credential-agent",
                "gpg",
                "load-interactive",
                "FINGERPRINT",
            ],
            check=False,
            stdin=streams.__enter__.return_value[0],
            stdout=streams.__enter__.return_value[1],
            stderr=streams.__enter__.return_value[1],
        )

    def test_sidecar_container_rejects_a_missing_sidecar(self) -> None:
        resource = _resources([_CredentialProtocol.GPG])[0]
        with (
            mock.patch.object(_resource_gpg, "get_docker_client"),
            mock.patch.object(_resource_gpg, "_find_container", return_value=None),
            self.assertRaisesRegex(DockerError, "unavailable"),
        ):
            _resource_gpg._sidecar_container(mock.Mock(), resource)
