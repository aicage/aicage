from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from unittest import TestCase, mock

import portalocker
from docker.errors import DockerException, NotFound

from aicage.docker.errors import DockerError
from aicage.runtime.credential_agent import _resources
from aicage.runtime.credential_agent._resource_lifecycle import _resource_lock
from aicage.runtime.credential_agent._resource_models import (
    _CredentialProtocol,
    _CredentialResource,
    _ImageSpec,
)
from aicage.runtime.credential_agent._resource_models import (
    _resources as _resource_definitions,
)


class CredentialAgentResourcesTests(TestCase):
    def setUp(self) -> None:
        self._ssh = _CredentialProtocol.SSH
        self._image = _ImageSpec("image:tag", "image-id", "1000:1000")
        self._resource = _resource_definitions([self._ssh], self._image.user)[0]
        self._labels = {
            "org.aicage.resource": "credential-agent",
            "org.aicage.credential-agent.protocol": "ssh",
            "org.aicage.credential-agent.owner": self._resource.owner,
            "org.aicage.credential-agent.image-id": "image-id",
        }

    def test__ensure_resources_creates_missing_volume_and_sidecar(self) -> None:
        client = mock.Mock()
        volume = mock.Mock(name=self._resource.volume_name, labels=self._labels)
        container = self._container(status="running")
        client.volumes.get.side_effect = NotFound("missing")
        client.volumes.create.return_value = volume
        client.containers.get.side_effect = NotFound("missing")
        client.containers.run.return_value = container

        with self._client(client):
            resources = _resources._ensure_resources([self._ssh], self._image)

        self.assertEqual([self._resource], resources)
        client.volumes.create.assert_called_once_with(
            name=self._resource.volume_name,
            labels={
                "org.aicage.resource": "credential-agent",
                "org.aicage.credential-agent.protocol": "ssh",
                "org.aicage.credential-agent.owner": self._resource.owner,
            },
        )
        client.containers.run.assert_called_once()
        self.assertTrue(client.containers.run.call_args.kwargs["network_disabled"])
        client.api.exec_create.assert_called_once_with(
            container.id,
            ["credential-agent", "ssh", "ready"],
            user=self._resource.user,
        )

    def test__ensure_resources_restarts_stopped_owned_sidecar(self) -> None:
        client = mock.Mock()
        volume = mock.Mock(name=self._resource.volume_name, labels=self._labels)
        container = self._container(status="exited")
        credentials = Path("/test-tmp/.ssh")
        container.attrs["Mounts"] = [
            {
                "Destination": self._resource.credential_directory.as_posix(),
                "Source": str(credentials),
            }
        ]
        client.volumes.get.return_value = volume
        client.containers.get.return_value = container

        with (
            self._client(client),
            mock.patch.object(_resources, "HOST_SSH_DIR", credentials),
            mock.patch.object(Path, "is_dir", return_value=True),
        ):
            _resources._ensure_resources([self._ssh], self._image)

        container.start.assert_called_once()
        container.remove.assert_not_called()
        client.containers.run.assert_not_called()

    def test__ensure_resources_keeps_windows_docker_desktop_sidecar(self) -> None:
        client = mock.Mock()
        volume = mock.Mock(name=self._resource.volume_name, labels=self._labels)
        container = self._container(status="running")
        credentials = Path("C:/Users/tester/.ssh")
        container.attrs["Mounts"] = [
            {
                "Destination": self._resource.credential_directory.as_posix(),
                "Source": "/run/desktop/mnt/host/c/Users/tester/.ssh",
            }
        ]
        client.volumes.get.return_value = volume
        client.containers.get.return_value = container

        with (
            self._client(client),
            mock.patch.object(_resources, "HOST_SSH_DIR", credentials),
            mock.patch.object(Path, "is_dir", return_value=True),
            mock.patch(
                "aicage.runtime.credential_agent._resource_lifecycle._os_name", "nt"
            ),
        ):
            _resources._ensure_resources(
                [self._ssh], _ImageSpec("image:tag", "image-id", "0:0")
            )

        container.remove.assert_not_called()

    def test__ensure_resources_replaces_an_obsolete_sidecar(self) -> None:
        client = mock.Mock()
        volume = mock.Mock(name=self._resource.volume_name, labels=self._labels)
        container = self._container(
            labels={**self._labels, "org.aicage.credential-agent.image-id": "old"},
            state={"Status": "running"},
        )
        client.volumes.get.return_value = volume
        client.containers.get.return_value = container
        client.containers.run.return_value = self._container(status="running")

        with self._client(client):
            _resources._ensure_resources([self._ssh], self._image)

        container.remove.assert_called_once_with(force=True)
        client.volumes.create.assert_not_called()

    def test__ensure_resources_rejects_unowned_volume(self) -> None:
        client = mock.Mock()
        client.volumes.get.return_value = mock.Mock(
            name=self._resource.volume_name,
            labels={},
        )

        with self._client(client), self.assertRaisesRegex(DockerError, "not owned"):
            _resources._ensure_resources([self._ssh], self._image)

    def test__ensure_resources_rejects_unowned_sidecar(self) -> None:
        client = mock.Mock()
        volume = mock.Mock(name=self._resource.volume_name, labels=self._labels)
        client.volumes.get.return_value = volume
        client.containers.get.return_value = self._container(labels={})

        with self._client(client), self.assertRaisesRegex(DockerError, "not owned"):
            _resources._ensure_resources([self._ssh], self._image)

    def test__ensure_resources_mounts_credentials_only_in_sidecar(self) -> None:
        client = mock.Mock()
        volume = mock.Mock(name=self._resource.volume_name, labels=self._labels)
        credentials = Path("/test-tmp/.ssh")
        client.volumes.get.return_value = volume
        client.containers.get.side_effect = NotFound("missing")
        client.containers.run.return_value = self._container(status="running")

        with (
            self._client(client),
            mock.patch.object(_resources, "HOST_SSH_DIR", credentials),
            mock.patch.object(Path, "is_dir", return_value=True),
        ):
            _resources._ensure_resources(
                [self._ssh],
                self._image,
            )

        sidecar_call = client.containers.run.call_args_list[0]
        self.assertEqual(
            {
                volume.name: {
                    "bind": "/run/credential-agent",
                    "mode": "rw",
                },
                str(credentials): {"bind": "/credential/ssh", "mode": "ro"},
            },
            sidecar_call.kwargs["volumes"],
        )

    def test__ensure_resources_reports_readiness_failure(self) -> None:
        client = mock.Mock()
        volume = mock.Mock(name=self._resource.volume_name, labels=self._labels)
        client.volumes.get.return_value = volume
        client.containers.get.side_effect = NotFound("missing")
        client.containers.run.return_value = self._container(status="running")
        client.api.exec_create.side_effect = DockerException("not ready")

        with (
            self._client(client),
            self.assertRaisesRegex(DockerError, "did not become ready"),
        ):
            _resources._ensure_resources([self._ssh], self._image)

    def test__ensure_resources_retries_transient_readiness_failure(self) -> None:
        client = mock.Mock()
        volume = mock.Mock(name=self._resource.volume_name, labels=self._labels)
        client.volumes.get.return_value = volume
        client.containers.get.side_effect = NotFound("missing")
        client.containers.run.return_value = self._container(status="running")
        client.api.exec_inspect.side_effect = [{"ExitCode": 1}, {"ExitCode": 0}]

        with (
            self._client(client),
            mock.patch(
                "aicage.runtime.credential_agent._resource_lifecycle.time.sleep"
            ) as sleep,
        ):
            _resources._ensure_resources([self._ssh], self._image)

        self.assertEqual(2, client.api.exec_create.call_count)
        sleep.assert_called_once_with(0.1)

    def test__ensure_resources_reconciles_after_releasing_resources_lock(self) -> None:
        client = mock.Mock()
        volume = mock.Mock(name=self._resource.volume_name, labels=self._labels)
        container = self._container(status="running")
        client.volumes.get.return_value = volume
        client.containers.get.return_value = container
        events: list[str] = []

        @contextmanager
        def resource_lock() -> Iterator[None]:
            events.append("locked")
            yield
            events.append("released")

        def reconcile(_resources: list[_CredentialResource]) -> None:
            events.append("reconciled")

        with (
            self._client(client),
            mock.patch.object(_resources, "_resource_lock", resource_lock),
        ):
            _resources._ensure_resources(
                [self._ssh],
                self._image,
                reconcile=reconcile,
            )

        self.assertEqual(["locked", "released", "reconciled"], events)

    def test_resource_lock_translates_contention_error(self) -> None:
        with (
            mock.patch(
                "aicage.runtime.credential_agent._resource_lifecycle.portalocker.Lock",
                side_effect=portalocker.exceptions.LockException,
            ),
            self.assertRaisesRegex(DockerError, "Failed to lock"),
        ):
            with _resource_lock():
                pass

    def test__resources_deduplicates_protocols(self) -> None:
        resources = _resource_definitions(
            [_CredentialProtocol.SSH, _CredentialProtocol.SSH]
        )

        self.assertEqual(1, len(resources))

    def test__ensure_resources_skips_empty_protocols(self) -> None:
        with mock.patch.object(_resources, "get_docker_client") as client:
            self.assertEqual([], _resources._ensure_resources([], self._image))

        client.assert_not_called()

    @contextmanager
    def _client(self, client: mock.Mock) -> Iterator[None]:
        client.api.exec_create.return_value = {"Id": "credential-ready"}
        client.api.exec_inspect.return_value = {"ExitCode": 0}
        with (
            mock.patch(
                "aicage.runtime.credential_agent._resources.get_docker_client",
                return_value=client,
            ),
            mock.patch.object(_resources, "_resource_lock", return_value=nullcontext()),
        ):
            yield

    def _container(
        self,
        *,
        status: str | None = None,
        labels: dict[str, str] | None = None,
        state: dict[str, object] | None = None,
    ) -> mock.Mock:
        container = mock.Mock(labels=self._labels if labels is None else labels)
        container.attrs = {"State": state or {"Status": status}}
        return container
