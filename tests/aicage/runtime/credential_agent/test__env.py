from unittest import TestCase, mock

from aicage.runtime.credential_agent import _env


class CredentialAgentEnvTests(TestCase):
    def test_credential_agent_user_uses_host_ids_on_posix(self) -> None:
        with (
            mock.patch.object(_env.os, "name", "posix"),
            mock.patch.object(_env, "_resolve_host_user_id", side_effect=[1000, 1001]),
            mock.patch.object(_env, "is_rootless_docker", return_value=False),
        ):
            self.assertEqual("1000:1001", _env._credential_agent_user())

    def test_credential_agent_user_uses_root_on_windows_or_rootless_docker(
        self,
    ) -> None:
        with mock.patch.object(_env.os, "name", "nt"):
            self.assertEqual("0:0", _env._credential_agent_user())

        with (
            mock.patch.object(_env.os, "name", "posix"),
            mock.patch.object(_env, "is_rootless_docker", return_value=True),
        ):
            self.assertEqual("0:0", _env._credential_agent_user())

    def test_resolve_host_user_id_handles_missing_host_apis(self) -> None:
        with mock.patch.dict(_env.os.__dict__, {"getuid": None}):
            self.assertIsNone(_env._resolve_host_user_id("getuid"))
