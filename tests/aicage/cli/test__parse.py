import io
from collections.abc import Sequence
from unittest import TestCase, mock

from aicage import __version__
from aicage.cli._errors import CliError
from aicage.cli._parse import parse_cli
from aicage.cli_types import (
    ConfigInfoArgs,
    ConfigRemoveArgs,
    ConfigUpdateArgs,
    ParsedArgs,
)
from aicage.config.errors import ConfigError


def _parse_run(argv: Sequence[str]) -> ParsedArgs:
    parsed = parse_cli(argv)
    if not isinstance(parsed, ParsedArgs):
        raise AssertionError(
            f"Expected a runnable command, got {type(parsed).__name__}."
        )
    return parsed


class ParseCliTests(TestCase):
    def test_parse_cli_with_docker_args(self) -> None:
        with self.assertRaises(CliError) as ctx:
            parse_cli(["--dry-run", "--network=host", "codex", "--foo"])
        self.assertEqual(
            "Docker args require '--' before the agent.", str(ctx.exception)
        )

    def test_parse_cli_with_separator(self) -> None:
        with mock.patch("sys.stdin.isatty", return_value=True):
            parsed = _parse_run(["--dry-run", "--", "codex", "--bar"])
        self.assertTrue(parsed.dry_run)
        self.assertEqual("ui", parsed.menu)
        self.assertEqual("", parsed.docker_args)
        self.assertEqual("codex", parsed.agent)
        self.assertEqual(["--bar"], parsed.agent_args)
        self.assertEqual([], parsed.shares)

    def test_parse_cli_with_separator_and_docker_args(self) -> None:
        with mock.patch("sys.stdin.isatty", return_value=True):
            parsed = _parse_run(
                [
                    "--dry-run",
                    "-v",
                    "/run/docker.sock:/run/docker.sock",
                    "--",
                    "codex",
                    "--bar",
                ]
            )
        self.assertTrue(parsed.dry_run)
        self.assertEqual("ui", parsed.menu)
        self.assertEqual("-v /run/docker.sock:/run/docker.sock", parsed.docker_args)
        self.assertEqual("codex", parsed.agent)
        self.assertEqual(["--bar"], parsed.agent_args)
        self.assertFalse(parsed.docker_socket)
        self.assertEqual([], parsed.shares)
        self.assertIsInstance(parsed, ParsedArgs)

    def test_parse_cli_without_docker_args(self) -> None:
        with mock.patch("sys.stdin.isatty", return_value=True):
            parsed = _parse_run(["codex", "--flag"])
        self.assertFalse(parsed.dry_run)
        self.assertEqual("ui", parsed.menu)
        self.assertEqual("", parsed.docker_args)
        self.assertEqual("codex", parsed.agent)
        self.assertEqual(["--flag"], parsed.agent_args)
        self.assertFalse(parsed.docker_socket)
        self.assertEqual([], parsed.shares)
        self.assertIsInstance(parsed, ParsedArgs)

    def test_parse_cli_agent_config_flag_after_agent(self) -> None:
        parsed = _parse_run(
            [
                "--menu",
                "none",
                "codex",
                "exec",
                "--config",
                "model_supports_reasoning_summaries=true",
            ]
        )
        self.assertEqual("none", parsed.menu)
        self.assertEqual("codex", parsed.agent)
        self.assertEqual(
            [
                "exec",
                "--config",
                "model_supports_reasoning_summaries=true",
            ],
            parsed.agent_args,
        )
        self.assertIsInstance(parsed, ParsedArgs)

    def test_parse_cli_flags_after_agent_are_agent_args(self) -> None:
        with mock.patch("sys.stdin.isatty", return_value=True):
            parsed = _parse_run(["codex", "--foo", "--menu", "none"])
        self.assertEqual("ui", parsed.menu)
        self.assertEqual("codex", parsed.agent)
        self.assertEqual(["--foo", "--menu", "none"], parsed.agent_args)

    def test_parse_cli_unknown_agent_preserves_config_flag_after_agent(self) -> None:
        parsed = _parse_run(["forge", "exec", "--config", "custom=true"])
        self.assertEqual("forge", parsed.agent)
        self.assertEqual(["exec", "--config", "custom=true"], parsed.agent_args)
        self.assertIsInstance(parsed, ParsedArgs)

    def test_parse_cli_uses_no_menu_without_tty(self) -> None:
        with mock.patch("sys.stdin.isatty", return_value=False):
            parsed = _parse_run(["codex"])

        self.assertEqual("none", parsed.menu)

    def test_parse_cli_preserves_explicit_ui_menu_without_tty(self) -> None:
        with mock.patch("sys.stdin.isatty", return_value=False):
            parsed = _parse_run(["--menu", "ui", "codex"])

        self.assertEqual("ui", parsed.menu)

    def test_parse_cli_help_exits(self) -> None:
        with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            with self.assertRaises(SystemExit) as ctx:
                parse_cli(["--help"])
        self.assertEqual(0, ctx.exception.code)
        self.assertIn("Usage:", stdout.getvalue())

    def test_parse_cli_version_exits(self) -> None:
        with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            with self.assertRaises(SystemExit) as ctx:
                parse_cli(["--version"])
        self.assertEqual(0, ctx.exception.code)
        self.assertEqual(f"{__version__}\n", stdout.getvalue())

    def test_parse_cli_short_version_exits(self) -> None:
        with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            with self.assertRaises(SystemExit) as ctx:
                parse_cli(["-v"])
        self.assertEqual(0, ctx.exception.code)
        self.assertEqual(f"{__version__}\n", stdout.getvalue())

    def test_parse_cli_requires_arguments(self) -> None:
        with self.assertRaises(CliError) as ctx:
            parse_cli([])
        self.assertIn("Missing argument. Provide an agent name", str(ctx.exception))
        self.assertIn("Available agents:", str(ctx.exception))

    def test_parse_cli_requires_agent_after_separator(self) -> None:
        with self.assertRaises(CliError):
            parse_cli(["--"])

    def test_parse_cli_requires_agent_name(self) -> None:
        with self.assertRaises(CliError):
            parse_cli([""])

    def test_parse_cli_requires_arguments_without_agent_list_on_config_error(
        self,
    ) -> None:
        with mock.patch(
            "aicage.cli._parse.load_bases", side_effect=ConfigError("broken")
        ):
            with self.assertRaises(CliError) as ctx:
                parse_cli([])
        self.assertEqual(
            "Missing argument. Provide an agent name.",
            str(ctx.exception),
        )

    def test_parse_cli_requires_separator_for_docker_args(self) -> None:
        with self.assertRaises(CliError) as ctx:
            parse_cli(["-v", "/test-tmp/folder:/test-tmp/folder", "codex"])
        self.assertEqual(
            "Docker args require '--' before the agent.", str(ctx.exception)
        )

    def test_parse_cli_config_info(self) -> None:
        parsed = parse_cli(["--config", "info"])
        assert isinstance(parsed, ConfigInfoArgs)
        self.assertIsNone(parsed.scope)

    def test_parse_cli_config_defaults_to_info(self) -> None:
        with mock.patch("sys.stdin.isatty", return_value=False):
            parsed = parse_cli(["--config"])
        assert isinstance(parsed, ConfigInfoArgs)
        self.assertIsNone(parsed.scope)

    def test_parse_cli_config_print_alias(self) -> None:
        parsed = parse_cli(["--config", "print"])
        assert isinstance(parsed, ConfigInfoArgs)

    def test_parse_cli_config_info_rejects_args(self) -> None:
        with self.assertRaises(CliError):
            parse_cli(["--config", "info", "codex"])

    def test_parse_cli_config_remove_requires_agent(self) -> None:
        with self.assertRaises(CliError) as ctx:
            parse_cli(["--config", "remove"])
        self.assertEqual(
            "Use '--config remove <agent>' or '--config remove <global|tree> <agent>'.",
            str(ctx.exception),
        )

    def test_parse_cli_config_remove_scope_requires_agent(self) -> None:
        with self.assertRaises(CliError) as ctx:
            parse_cli(["--config", "remove", "global"])
        self.assertEqual(
            "Use '--config remove <agent>' or '--config remove <global|tree> <agent>'.",
            str(ctx.exception),
        )

    def test_parse_cli_config_remove_with_agent(self) -> None:
        parsed = parse_cli(["--config", "remove", "codex"])
        assert isinstance(parsed, ConfigRemoveArgs)
        self.assertEqual("codex", parsed.agent)
        self.assertIsNone(parsed.scope)

    def test_parse_cli_config_info_rejects_agent(self) -> None:
        with self.assertRaises(CliError) as ctx:
            parse_cli(["--config", "info", "codex"])
        self.assertEqual("Use '--config info [global|tree]'.", str(ctx.exception))

    def test_parse_cli_config_info_global(self) -> None:
        parsed = parse_cli(["--config", "info", "global"])

        assert isinstance(parsed, ConfigInfoArgs)
        self.assertEqual("global", parsed.scope)

    def test_parse_cli_config_remove_tree_agent(self) -> None:
        parsed = parse_cli(["--config", "remove", "tree", "codex"])

        assert isinstance(parsed, ConfigRemoveArgs)
        self.assertEqual("tree", parsed.scope)
        self.assertEqual("codex", parsed.agent)

    def test_parse_cli_config_global_update_with_docker_args(self) -> None:
        parsed = parse_cli(
            [
                "--menu",
                "none",
                "-e",
                "GLOBAL_VAR=0",
                "--docker",
                "--share",
                "data",
                "--extension",
                "gh",
                "--git",
                "--config",
                "global",
                "--",
                "codex",
            ]
        )

        assert isinstance(parsed, ConfigUpdateArgs)
        self.assertEqual("global", parsed.scope)
        self.assertEqual("codex", parsed.agent)
        self.assertEqual("-e GLOBAL_VAR=0", parsed.docker_args)
        self.assertEqual("none", parsed.menu)
        self.assertTrue(parsed.docker_socket)
        self.assertEqual(["data"], parsed.shares)
        self.assertEqual(["gh"], parsed.extensions)
        self.assertTrue(parsed.git)

    def test_parse_cli_config_update_rejects_agent_args(self) -> None:
        with self.assertRaises(CliError) as ctx:
            parse_cli(["--config", "tree", "--", "codex", "exec"])

        self.assertEqual(
            "Configuration updates require exactly one agent after '--'.",
            str(ctx.exception),
        )

    def test_parse_cli_config_update_rejects_dry_run(self) -> None:
        with self.assertRaises(CliError) as ctx:
            parse_cli(["--dry-run", "--config", "global", "--", "codex"])

        self.assertEqual(
            "--dry-run cannot be used when updating configuration.",
            str(ctx.exception),
        )

    def test_parse_cli_config_update_rejects_acp_wsl(self) -> None:
        with self.assertRaises(CliError) as ctx:
            parse_cli(["--acp-wsl", "--config", "global", "--", "codex"])

        self.assertEqual(
            "--acp-wsl cannot be used when updating configuration.",
            str(ctx.exception),
        )

    def test_parse_cli_accepts_git_for_agent(self) -> None:
        parsed = _parse_run(["--git", "--", "codex"])

        self.assertEqual("codex", parsed.agent)
        self.assertTrue(parsed.git)

    def test_parse_cli_accepts_bare_git_for_agent(self) -> None:
        parsed = _parse_run(["--git", "codex"])

        self.assertEqual("codex", parsed.agent)
        self.assertTrue(parsed.git)

    def test_parse_cli_accepts_git_off_for_agent(self) -> None:
        parsed = _parse_run(["--git", "off", "codex"])

        self.assertEqual("codex", parsed.agent)
        self.assertFalse(parsed.git)

    def test_parse_cli_leaves_git_unset_without_option(self) -> None:
        parsed = _parse_run(["codex"])

        self.assertIsNone(parsed.git)

    def test_parse_cli_config_info_rejects_git_off(self) -> None:
        with self.assertRaises(CliError) as ctx:
            parse_cli(["--git", "off", "--config", "info"])

        self.assertEqual(
            "No additional arguments are allowed with --config.", str(ctx.exception)
        )

    def test_parse_cli_config_rejects_too_many_values(self) -> None:
        with self.assertRaises(CliError) as ctx:
            parse_cli(["--config", "remove", "codex", "extra"])
        self.assertEqual(
            "Use '--config remove <agent>' or '--config remove <global|tree> <agent>'.",
            str(ctx.exception),
        )

    def test_parse_cli_flags_before_separator(self) -> None:
        parsed = _parse_run(
            [
                "--docker",
                "--dry-run",
                "--",
                "codex",
            ]
        )
        self.assertTrue(parsed.dry_run)
        self.assertTrue(parsed.docker_socket)
        self.assertEqual("", parsed.docker_args)
        self.assertEqual("codex", parsed.agent)
        self.assertEqual([], parsed.shares)

    def test_parse_cli_with_share(self) -> None:
        parsed = _parse_run(
            ["--share", "data", "--share", "/test-tmp/one:ro", "--", "codex"]
        )
        self.assertEqual(["data", "/test-tmp/one:ro"], parsed.shares)

    def test_parse_cli_with_extensions(self) -> None:
        parsed = _parse_run(["--extension", "one", "--extension", "two", "--", "codex"])

        self.assertEqual(["one", "two"], parsed.extensions)

    def test_parse_cli_with_acp_wsl(self) -> None:
        parsed = _parse_run(["--acp-wsl", "--", "codex"])

        self.assertTrue(parsed.acp_wsl)

    def test_parse_cli_with_base(self) -> None:
        parsed = _parse_run(["--base", "ubuntu", "--", "codex"])

        self.assertEqual("ubuntu", parsed.base)

    def test_parse_cli_with_menu_none(self) -> None:
        parsed = _parse_run(["--menu", "none", "codex"])
        self.assertEqual("none", parsed.menu)
        self.assertEqual("codex", parsed.agent)

    def test_parse_cli_rejects_simple_menu(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            parse_cli(["--menu", "simple", "codex"])

        self.assertEqual(2, ctx.exception.code)

    def test_parse_cli_config_rejects_share(self) -> None:
        with self.assertRaises(CliError):
            parse_cli(["--config", "info", "--share", "data"])

    def test_parse_cli_config_rejects_extension(self) -> None:
        with self.assertRaises(CliError):
            parse_cli(["--config", "info", "--extension", "one"])

    def test_parse_cli_config_rejects_base(self) -> None:
        with self.assertRaises(CliError):
            parse_cli(["--config", "info", "--base", "ubuntu"])

    def test_parse_cli_config_rejects_non_default_menu(self) -> None:
        with self.assertRaises(CliError):
            parse_cli(["--config", "info", "--menu", "none"])

    def test_parse_cli_help_shows_config_default(self) -> None:
        with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            with self.assertRaises(SystemExit):
                parse_cli(["--help"])

        output = stdout.getvalue()
        self.assertIn("aicage --config\n", output)
        self.assertIn(
            "--config [<command>] Inspect or change saved configuration; see usage above.",
            output,
        )
        self.assertIn("--menu <mode>", output)
        self.assertIn("[--git [on|off]]", output)
        self.assertIn("[--base <id>]", output)
        self.assertIn("[--extension <id>]...", output)
        self.assertIn("--base <id>      Select the agent base image.", output)
        self.assertIn(
            "--git [on|off]   Enable or disable Git support mounts (default: on).",
            output,
        )
        self.assertNotIn("simple", output)
        self.assertNotIn("--stdio", output)
