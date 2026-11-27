from pathlib import Path
from unittest import TestCase, mock

from aicage.docker._env import resolve_user_ids


class EnvTests(TestCase):
    def test_resolve_user_ids_handles_missing(self) -> None:
        with (
            mock.patch("aicage.docker._env.os.getuid", None, create=True),
            mock.patch("aicage.docker._env.os.getgid", None, create=True),
            mock.patch.dict(
                "aicage.docker._env.os.environ",
                {"USER": "tester"},
                clear=True,
            ),
            mock.patch(
                "aicage.docker._env.Path.home",
                return_value=Path("/home/tester"),
            ),
            mock.patch("aicage.docker._env.os.name", "posix"),
            mock.patch(
                "aicage.docker._env.is_rootless_docker",
                return_value=False,
            ),
        ):
            env_flags = resolve_user_ids()
        self.assertEqual(
            [
                "-e",
                "AICAGE_HOST_USER=tester",
                "-e",
                "AICAGE_HOME=/home/tester",
            ],
            env_flags,
        )

    def test_resolve_user_ids_includes_uid_gid(self) -> None:
        with (
            mock.patch(
                "aicage.docker._env.os.getuid",
                return_value=1000,
                create=True,
            ),
            mock.patch(
                "aicage.docker._env.os.getgid",
                return_value=1001,
                create=True,
            ),
            mock.patch.dict(
                "aicage.docker._env.os.environ",
                {"USER": "tester"},
                clear=True,
            ),
            mock.patch(
                "aicage.docker._env.Path.home",
                return_value=Path("/home/tester"),
            ),
            mock.patch("aicage.docker._env.os.name", "posix"),
            mock.patch(
                "aicage.docker._env.is_rootless_docker",
                return_value=False,
            ),
        ):
            env_flags = resolve_user_ids()
        self.assertEqual(
            [
                "-e",
                "AICAGE_UID=1000",
                "-e",
                "AICAGE_GID=1001",
                "-e",
                "AICAGE_HOST_USER=tester",
                "-e",
                "AICAGE_HOME=/home/tester",
            ],
            env_flags,
        )

    def test_resolve_user_ids_rootless_linux_uses_root_with_mount_home(self) -> None:
        with (
            mock.patch(
                "aicage.docker._env.os.getuid",
                return_value=1000,
                create=True,
            ),
            mock.patch(
                "aicage.docker._env.os.getgid",
                return_value=1001,
                create=True,
            ),
            mock.patch.dict(
                "aicage.docker._env.os.environ",
                {"USER": "tester"},
                clear=True,
            ),
            mock.patch(
                "aicage.docker._env.Path.home",
                return_value=Path("/home/tester"),
            ),
            mock.patch("aicage.docker._env.os.name", "posix"),
            mock.patch(
                "aicage.docker._env.is_rootless_docker",
                return_value=True,
            ),
        ):
            env_flags = resolve_user_ids()
        self.assertEqual(
            [
                "-e",
                "AICAGE_UID=0",
                "-e",
                "AICAGE_GID=0",
                "-e",
                "AICAGE_HOST_USER=root",
                "-e",
                "AICAGE_HOME=/root",
                "-e",
                "AICAGE_MOUNT_HOME=/home/tester",
            ],
            env_flags,
        )

    def test_resolve_user_ids_sets_root_on_windows(self) -> None:
        with (
            mock.patch(
                "aicage.docker._env.os.getuid",
                side_effect=AttributeError,
                create=True,
            ),
            mock.patch(
                "aicage.docker._env.os.getgid",
                side_effect=AttributeError,
                create=True,
            ),
            mock.patch.dict(
                "aicage.docker._env.os.environ",
                {"USER": "tester"},
                clear=True,
            ),
            mock.patch(
                "aicage.docker._env.Path.home",
                return_value=Path(r"D:\Users\tester"),
            ),
            mock.patch("aicage.docker._env.os.name", "nt"),
        ):
            env_flags = resolve_user_ids()
        self.assertEqual(
            [
                "-e",
                "AICAGE_UID=0",
                "-e",
                "AICAGE_GID=0",
                "-e",
                "AICAGE_HOST_USER=root",
                "-e",
                "AICAGE_HOME=/root",
                "-e",
                "AICAGE_MOUNT_HOME=/mnt/d/Users/tester",
            ],
            env_flags,
        )
