import subprocess
from pathlib import Path
from unittest import TestCase, mock

from aicage.docker.build import _common

from ..._run_config_fixtures import build_run_config as _build_run_config


class CommonBuildTests(TestCase):
    def test_build_context_dir(self) -> None:
        run_config = _build_run_config(
            local_definition_dir=Path("/test-tmp/build/agents/claude")
        )

        context_dir = _common.build_context_dir(
            run_config, Path("/test-tmp/build/Dockerfile")
        )

        self.assertEqual(Path("/test-tmp/build"), context_dir)

    def test_run_build_command(self) -> None:
        reporter = mock.Mock()
        process = mock.Mock()
        process.stdout = iter(["step 1\n", "step 2\n"])
        process.wait.return_value = 0
        popen_context = mock.Mock()
        popen_context.__enter__ = mock.Mock(return_value=process)
        popen_context.__exit__ = mock.Mock(return_value=None)
        log_handle = mock.Mock()

        with (
            mock.patch.dict("aicage.docker.execution.cli.os.environ", {}, clear=True),
            mock.patch(
                "aicage.docker.build._common.subprocess.Popen",
                return_value=popen_context,
            ) as popen_mock,
            mock.patch("aicage.docker.build._common.register_process") as register_mock,
        ):
            returncode = _common.run_build_command(
                ["docker", "build"], log_handle, reporter
            )

        self.assertEqual(0, returncode)
        popen_mock.assert_called_once_with(
            ["docker", "build"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            env={"DOCKER_CLI_HINTS": "false"},
        )
        register_mock.assert_called_once_with(process)
