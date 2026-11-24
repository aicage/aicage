from pathlib import Path
from unittest import TestCase, mock

from aicage.docker import runtime


class DockerRuntimeTests(TestCase):
    def setUp(self) -> None:
        runtime.get_active_docker_host.cache_clear()
        runtime._is_rootless_docker.cache_clear()

    def tearDown(self) -> None:
        runtime.get_active_docker_host.cache_clear()
        runtime._is_rootless_docker.cache_clear()

    def test_get_active_docker_host_prefers_env(self) -> None:
        with mock.patch.dict(
            "aicage.docker.runtime.os.environ",
            {"DOCKER_HOST": "unix:///run/user/1000/docker.sock"},
            clear=True,
        ):
            host = runtime.get_active_docker_host()

        self.assertEqual("unix:///run/user/1000/docker.sock", host.host)
        self.assertEqual(Path("/run/user/1000/docker.sock"), host.socket_path)
        self.assertIsNone(host.named_pipe_path)

    def test_get_active_docker_host_parses_named_pipe(self) -> None:
        with mock.patch.dict(
            "aicage.docker.runtime.os.environ",
            {"DOCKER_HOST": "npipe:////./pipe/docker_engine"},
            clear=True,
        ):
            host = runtime.get_active_docker_host()

        self.assertIsNone(host.socket_path)
        self.assertEqual(Path(r"\\.\pipe\docker_engine"), host.named_pipe_path)

    def test_get_active_docker_host_reads_context(self) -> None:
        process = mock.Mock(stdout='"unix:///run/user/1000/docker.sock"\n')
        with (
            mock.patch.dict("aicage.docker.runtime.os.environ", {}, clear=True),
            mock.patch(
                "aicage.docker.runtime.run_docker_command_capture", return_value=process
            ),
        ):
            host = runtime.get_active_docker_host()

        self.assertEqual("unix:///run/user/1000/docker.sock", host.host)
        self.assertEqual(Path("/run/user/1000/docker.sock"), host.socket_path)

    def test_get_active_docker_host_falls_back_to_default(self) -> None:
        with (
            mock.patch.dict("aicage.docker.runtime.os.environ", {}, clear=True),
            mock.patch(
                "aicage.docker.runtime.run_docker_command_capture",
                side_effect=RuntimeError("boom"),
            ),
        ):
            host = runtime.get_active_docker_host()

        self.assertEqual("unix:///run/docker.sock", host.host)
        self.assertEqual(Path("/run/docker.sock"), host.socket_path)

    def test__is_rootless_docker_detects_rootless_security_option(self) -> None:
        process = mock.Mock(stdout='["name=seccomp","name=rootless"]\n')
        with (
            mock.patch("aicage.docker.runtime.os.name", "posix"),
            mock.patch(
                "aicage.docker.runtime.run_docker_command_capture", return_value=process
            ),
        ):
            self.assertTrue(runtime._is_rootless_docker())

    def test__is_rootless_docker_returns_false_when_not_rootless(self) -> None:
        process = mock.Mock(stdout='["name=seccomp"]\n')
        with (
            mock.patch("aicage.docker.runtime.os.name", "posix"),
            mock.patch(
                "aicage.docker.runtime.run_docker_command_capture", return_value=process
            ),
        ):
            self.assertFalse(runtime._is_rootless_docker())
