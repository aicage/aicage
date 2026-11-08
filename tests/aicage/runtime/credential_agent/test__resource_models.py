from pathlib import Path
from unittest import TestCase, mock

from aicage.runtime.credential_agent import _resource_models


class CredentialResourceModelsTests(TestCase):
    def test__resource_owner_uses_the_host_uid(self) -> None:
        with mock.patch.object(
            _resource_models, "_resolve_host_user_id", return_value=1000
        ):
            owner = _resource_models._resource_owner()

        self.assertEqual("u1000", owner)

    def test__resource_owner_uses_the_home_hash_without_a_host_uid(self) -> None:
        with (
            mock.patch.object(
                _resource_models, "_resolve_host_user_id", return_value=None
            ),
            mock.patch.object(Path, "home", return_value=Path("Tester")),
        ):
            owner = _resource_models._resource_owner()

        self.assertEqual("w9bba5c53a054", owner)
