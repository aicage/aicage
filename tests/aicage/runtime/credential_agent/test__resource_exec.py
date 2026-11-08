from unittest import TestCase, mock

from aicage.docker.errors import DockerError
from aicage.runtime.credential_agent import _resource_exec


class ResourceExecTests(TestCase):
    def test_close_exec_stream_closes_retained_response_before_stream(self) -> None:
        stream = mock.Mock()
        response = mock.Mock()
        stream.attach_mock(response, "_response")

        _resource_exec.close_exec_stream(stream)

        self.assertEqual(
            [mock.call._response.close(), mock.call.close()], stream.mock_calls
        )

    def test_write_exec_input_uses_socket_io_socket_when_stream_is_not_writable(
        self,
    ) -> None:
        socket = mock.Mock()
        stream = mock.Mock(spec=["_sock", "writable"])
        stream._sock = socket
        stream.writable.return_value = False

        _resource_exec.write_exec_input(stream, b"secret\n")

        socket.sendall.assert_called_once_with(b"secret\n")

    def test_write_exec_input_uses_socket_io_write_when_sendall_is_unavailable(
        self,
    ) -> None:
        stream = mock.Mock(spec=["write"])
        stream.write.return_value = 7

        _resource_exec.write_exec_input(stream, b"secret\n")

        stream.write.assert_called_once_with(b"secret\n")

    def test_terminal_streams_returns_process_terminal_streams(self) -> None:
        stdin = mock.Mock()
        stdout = mock.Mock()
        stdin.isatty.return_value = True
        stdout.isatty.return_value = True
        with (
            mock.patch.object(_resource_exec.sys, "stdin", stdin),
            mock.patch.object(_resource_exec.sys, "stdout", stdout),
        ):
            with _resource_exec.terminal_streams() as streams:
                self.assertEqual((stdin, stdout), streams)

    def test_terminal_streams_rejects_noninteractive_input(self) -> None:
        stdin = mock.Mock()
        stdout = mock.Mock()
        stdin.isatty.return_value = False
        with (
            mock.patch.object(_resource_exec.sys, "stdin", stdin),
            mock.patch.object(_resource_exec.sys, "stdout", stdout),
            self.assertRaisesRegex(DockerError, "interactive terminal"),
        ):
            with _resource_exec.terminal_streams():
                pass

    def test_wait_for_exec_completion_polls_until_the_exec_finishes(self) -> None:
        client = mock.Mock()
        client.api.exec_inspect.side_effect = [
            {"Running": True, "ExitCode": None},
            {"Running": False, "ExitCode": 0},
        ]
        with mock.patch.object(_resource_exec.time, "sleep"):
            result = _resource_exec.wait_for_exec_completion(client, "exec-id")

        self.assertEqual({"Running": False, "ExitCode": 0}, result)
        self.assertEqual(2, client.api.exec_inspect.call_count)
