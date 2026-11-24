import os
import subprocess
from pathlib import Path, PurePosixPath
from unittest import TestCase, mock

from aicage.docker import run
from aicage.runtime.run_args import BindMountSpec, DockerRunArgs, EnvVar


class RunCommandTests(TestCase):
    @staticmethod
    def test_run_container_executes_command() -> None:
        args = DockerRunArgs(
            image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
            merged_docker_args="",
            agent_args=["--flag"],
        )
        with (
            mock.patch(
                "aicage.docker.run._assemble_docker_run", return_value=["docker", "run"]
            ),
            mock.patch("aicage.docker.execution.cli.run_docker_command") as run_mock,
            mock.patch(
                "aicage.docker.run.get_local_repo_digest_for_repo",
                return_value="sha256:old",
            ),
            mock.patch("aicage.docker.run.cleanup_old_digest") as cleanup_mock,
        ):
            run.run_container(args)

        run_mock.assert_called_once_with(["docker", "run"], check=True)
        cleanup_mock.assert_called_once_with(
            "ghcr.io/aicage/aicage",
            "sha256:old",
            "ghcr.io/aicage/aicage:codex-ubuntu",
        )

    @staticmethod
    def test_print_run_command_outputs_command() -> None:
        args = DockerRunArgs(
            image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
            merged_docker_args="",
            agent_args=[],
        )
        with (
            mock.patch(
                "aicage.docker.run._assemble_docker_run",
                return_value=["docker", "run", "image"],
            ),
            mock.patch("builtins.print") as print_mock,
        ):
            run.print_run_command(args)

        print_mock.assert_called_once_with("docker run image")

    def test_run_builder_version_check_returns_output(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch(
                "aicage.docker.run.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    [], 0, stdout="1.2.3\n", stderr=""
                ),
            ),
        ):
            result = run.run_builder_version_check(
                "ghcr.io/aicage/aicage-image-util:agent-version",
                Path("/test-tmp/agent"),
            )
        self.assertEqual(0, result.returncode)
        self.assertEqual("1.2.3\n", result.stdout)
        self.assertEqual("", result.stderr)

    def test_run_builder_version_check_handles_command_error(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch(
                "aicage.docker.run.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    [], 2, stdout="partial", stderr="failed"
                ),
            ),
        ):
            result = run.run_builder_version_check(
                "ghcr.io/aicage/aicage-image-util:agent-version",
                Path("/test-tmp/agent"),
            )
        self.assertEqual(2, result.returncode)
        self.assertEqual("partial", result.stdout)
        self.assertEqual("failed", result.stderr)

    def test_run_builder_version_check_handles_timeout(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch(
                "aicage.docker.run.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd=["docker"], timeout=1),
            ),
        ):
            result = run.run_builder_version_check(
                "ghcr.io/aicage/aicage-image-util:agent-version",
                Path("/test-tmp/agent"),
            )
        self.assertEqual(124, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertEqual("Version check timed out.", result.stderr)

    def test_run_builder_version_check_handles_command_exception(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch(
                "aicage.docker.run.subprocess.run",
                side_effect=RuntimeError("boom"),
            ),
        ):
            result = run.run_builder_version_check(
                "ghcr.io/aicage/aicage-image-util:agent-version",
                Path("/test-tmp/agent"),
            )
        self.assertEqual(1, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertEqual("boom", result.stderr)

    def test_run_builder_version_check_includes_proxy_env_args(self) -> None:
        with (
            mock.patch.dict(
                os.environ,
                {"HTTPS_PROXY": "http://proxy-https:8080"},
                clear=True,
            ),
            mock.patch(
                "aicage.docker.run.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, stdout="ok", stderr=""),
            ) as run_mock,
        ):
            run.run_builder_version_check(
                "ghcr.io/aicage/aicage-image-util:agent-version",
                Path("/test-tmp/agent"),
            )

        command = run_mock.call_args.args[0]
        self.assertIn("-e", command)
        self.assertIn("HTTPS_PROXY=http://proxy-https:8080", command)

    def test_assemble_includes_env_and_mounts(self) -> None:
        with mock.patch(
            "aicage.docker.run.resolve_user_ids",
            return_value=["-e", "AICAGE_HOST_USER=me"],
        ):
            run_args = DockerRunArgs(
                image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
                merged_docker_args="--net=host",
                agent_args=["--flag"],
                env=[EnvVar(name="EXTRA", value="1")],
                mounts=[
                    BindMountSpec(
                        host_path=Path("/test-tmp/one"),
                        container_path=PurePosixPath("/opt/one"),
                        read_only=True,
                    )
                ],
            )
            cmd = run._assemble_docker_run(run_args)
        self.assertIn("-e", cmd)
        self.assertIn("EXTRA=1", cmd)
        self.assertIn("--mount", cmd)
        host_mount = Path("/test-tmp/one").as_posix()
        container_mount = PurePosixPath("/opt/one").as_posix()
        self.assertIn(f"type=bind,src={host_mount},dst={container_mount},readonly", cmd)
        self.assertNotIn("AICAGE_AGENT_CONFIG_PATH", " ".join(cmd))

    def test_assemble_uses_interactive_tty_when_stdin_is_tty(self) -> None:
        with (
            mock.patch("aicage.docker.run.resolve_user_ids", return_value=[]),
            mock.patch("sys.stdin.isatty", return_value=True),
        ):
            cmd = run._assemble_docker_run(
                DockerRunArgs(
                    image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
                    merged_docker_args="",
                    agent_args=[],
                )
            )

        self.assertIn("-it", cmd)

    def test_assemble_uses_stdin_without_tty_when_stdin_is_not_tty(self) -> None:
        with (
            mock.patch("aicage.docker.run.resolve_user_ids", return_value=[]),
            mock.patch("sys.stdin.isatty", return_value=False),
        ):
            cmd = run._assemble_docker_run(
                DockerRunArgs(
                    image_ref="ghcr.io/aicage/aicage:codex-ubuntu",
                    merged_docker_args="",
                    agent_args=["exec", "--experimental-json"],
                )
            )

        self.assertIn("-i", cmd)
        self.assertNotIn("-it", cmd)
