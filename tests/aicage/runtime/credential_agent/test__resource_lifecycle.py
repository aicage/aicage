from pathlib import Path
from unittest import TestCase, mock

from aicage.runtime.credential_agent import _resource_lifecycle
from aicage.runtime.credential_agent._resource_models import (
    _CredentialProtocol,
    _resources,
)


class ResourceLifecycleTests(TestCase):
    def test_ssh_tmpfs_mounts_uses_the_target_key_directory(self) -> None:
        definition = _resources([_CredentialProtocol.SSH])[0]

        self.assertEqual(
            {"/test-tmp/.ssh": "rw,uid=1000,gid=1001,mode=0700"},
            _resource_lifecycle._ssh_tmpfs_mounts(
                definition, Path("/test-tmp/.ssh"), "1000:1001"
            ),
        )

    def test_gpg_has_no_ssh_tmpfs_mounts(self) -> None:
        definition = _resources([_CredentialProtocol.GPG])[0]

        self.assertEqual(
            {},
            _resource_lifecycle._ssh_tmpfs_mounts(
                definition, Path("/test-tmp/.gnupg"), "1000:1001"
            ),
        )

    def test_labels_for_reads_attributes_and_config_labels(self) -> None:
        resource = mock.Mock(
            labels=None,
            attrs={"Labels": "invalid", "Config": {"Labels": {"name": "value"}}},
        )

        self.assertEqual({"name": "value"}, _resource_lifecycle._labels_for(resource))

    def test_credential_mount_path_reads_matching_source(self) -> None:
        definition = _resources([_CredentialProtocol.SSH])[0]
        container = mock.Mock(
            attrs={
                "Mounts": [
                    {
                        "Destination": definition.credential_directory.as_posix(),
                        "Source": "/test-tmp/.ssh",
                    }
                ]
            }
        )

        self.assertEqual(
            Path("/test-tmp/.ssh"),
            _resource_lifecycle._credential_mount_path(container, definition),
        )

    def test_credential_mount_path_rejects_non_list_mounts(self) -> None:
        definition = _resources([_CredentialProtocol.SSH])[0]
        container = mock.Mock(attrs={"Mounts": "invalid"})

        self.assertIsNone(
            _resource_lifecycle._credential_mount_path(container, definition)
        )
