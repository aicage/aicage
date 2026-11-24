import tempfile
from pathlib import Path
from unittest import TestCase, mock

from aicage.errors import AicageError
from aicage.paths import container_project_path
from aicage.runtime.docker_args.resolve import resolver
from aicage.runtime.run_args import BindMountSpec


class HomeGuardTests(TestCase):
    def test_validate_home_mount_safety_rejects_home_mount(self) -> None:
        home_path = Path("/test-tmp/home").resolve()
        mounts = [
            BindMountSpec(
                host_path=home_path, container_path=container_project_path(home_path)
            ),
        ]

        with self.assertRaises(AicageError) as ctx:
            resolver._validate_home_mount_safety(mounts, home_path)

        self.assertEqual(
            "Refusing to start: this would expose your home directory to the container via "
            f"{home_path}.\n"
            "Use one of these safer options instead:\n"
            "- Start aicage from the project repository directory. If needed, add folders and files "
            "outside it with `--share <path>`.\n"
            "- For multi-project setups, keep repositories under a directory such as "
            "~/workspace and start aicage from there.",
            str(ctx.exception),
        )

    def test_validate_home_mount_safety_rejects_parent_of_home_mount(self) -> None:
        home_path = Path("/test-tmp/home/user").resolve()
        mounts = [
            BindMountSpec(
                host_path=home_path.parent,
                container_path=container_project_path(home_path.parent),
            ),
        ]

        with self.assertRaises(AicageError) as ctx:
            resolver._validate_home_mount_safety(mounts, home_path)

        self.assertEqual(
            "Refusing to start: this would expose your home directory to the container via "
            f"{home_path.parent}.\n"
            "Use one of these safer options instead:\n"
            "- Start aicage from the project repository directory. If needed, add folders and files "
            "outside it with `--share <path>`.\n"
            "- For multi-project setups, keep repositories under a directory such as "
            "~/workspace and start aicage from there.",
            str(ctx.exception),
        )

    @staticmethod
    def test_validate_home_mount_safety_allows_non_home_mount() -> None:
        home_path = Path("/test-tmp/home").resolve()
        mounts = [
            BindMountSpec(
                host_path=Path("/test-tmp/project"),
                container_path=container_project_path(Path("/test-tmp/project")),
            ),
        ]

        resolver._validate_home_mount_safety(mounts, home_path)

    @staticmethod
    def test_resolve_docker_args_uses_home_guard() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_path = Path(temp_dir) / "home"
            project_path = Path(temp_dir) / "project"
            home_path.mkdir()
            project_path.mkdir()

            with (
                mock.patch(
                    "aicage.runtime.docker_args.resolve.resolver._validate_home_mount_safety"
                ) as guard_mock,
                mock.patch(
                    "aicage.runtime.docker_args.resolve.resolver._resolver_sequence",
                    return_value=(),
                ),
                mock.patch(
                    "aicage.runtime.docker_args.resolve.resolver.Path.home",
                    return_value=home_path,
                ),
            ):
                context = mock.Mock()
                context.project_cfg = mock.Mock(path=str(project_path))
                context.project_cfg.agents = mock.Mock()
                agent_cfg = mock.Mock()
                agent_cfg.extensions = []
                agent_cfg.extension_mounts = {}
                context.project_cfg.agents.setdefault.return_value = agent_cfg
                context.extensions = {}
                resolver.resolve_docker_args(context, "codex", None)

        guard_mock.assert_called_once()
