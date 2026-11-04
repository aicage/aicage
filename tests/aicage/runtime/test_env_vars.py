from unittest import TestCase

from aicage.runtime import env_vars


class EnvVarsTests(TestCase):
    def test_constants(self) -> None:
        self.assertEqual("AICAGE_UID", env_vars.AICAGE_UID)
        self.assertEqual("AICAGE_GID", env_vars.AICAGE_GID)
        self.assertEqual("AICAGE_HOST_USER", env_vars.AICAGE_HOST_USER)
        self.assertEqual("AICAGE_HOME", env_vars.AICAGE_HOME)
        self.assertEqual("AICAGE_MOUNT_HOME", env_vars.AICAGE_MOUNT_HOME)
        self.assertEqual("AICAGE_ACP_WSL", env_vars._AICAGE_ACP_WSL)
        self.assertEqual("AICAGE_WORKSPACE", env_vars._AICAGE_WORKSPACE)
