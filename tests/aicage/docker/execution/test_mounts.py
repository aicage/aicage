from pathlib import Path, PurePosixPath
from unittest import TestCase

from aicage.docker.execution.mounts import mount_args
from aicage.runtime.run_args import BindMountSpec


class MountsTests(TestCase):
    def test_mount_args_returns_a_read_write_bind_mount(self) -> None:
        args = mount_args([BindMountSpec(Path("/host"), PurePosixPath("/container"))])
        self.assertEqual(["--mount", "type=bind,src=/host,dst=/container"], args)

    def test_mount_args_returns_a_read_only_bind_mount(self) -> None:
        args = mount_args(
            [BindMountSpec(Path("/host"), PurePosixPath("/container"), read_only=True)]
        )
        self.assertEqual(
            ["--mount", "type=bind,src=/host,dst=/container,readonly"], args
        )
