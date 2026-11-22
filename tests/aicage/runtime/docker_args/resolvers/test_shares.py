import tempfile
from pathlib import Path
from unittest import TestCase, mock

from aicage.cli_types import ParsedArgs
from aicage.config.context import ConfigContext
from aicage.config.extensions.loader import ExtensionMetadata
from aicage.config.project_config import AgentConfig, _ProjectConfig
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest, ResolvedArgs
from aicage.runtime.docker_args.resolvers import shares


class ShareResolverTests(TestCase):
    def test_resolve_returns_empty_when_no_shares_exist(self) -> None:
        context = ConfigContext(
            store=mock.Mock(),
            project_cfg=_ProjectConfig(path="/test-tmp/project", agents={}),
            agents={},
            bases={},
            extensions={},
        )

        self.assertEqual(ResolvedArgs(), shares.resolve(context, "codex", None))

    def test_resolve_uses_persisted_agent_shares_when_parsed_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cwd = Path(tmp_dir)
            project_cfg = _ProjectConfig(
                path=str(cwd / "project"),
                agents={"codex": AgentConfig(shares=["data:ro"])},
            )
            context = ConfigContext(
                store=mock.Mock(),
                project_cfg=project_cfg,
                agents={},
                bases={},
                extensions={},
            )

            with mock.patch(
                "aicage.runtime.docker_args.resolvers.shares.Path.cwd", return_value=cwd
            ):
                resolved = shares.resolve(context, "codex", None)

        expected_path = (cwd / "data").resolve()
        self.assertEqual(
            ResolvedArgs(
                mounts=[MountRequest(host_path=expected_path, read_only=True)]
            ),
            resolved,
        )

    def test_resolve_uses_persisted_agent_shares_when_parsed_has_no_shares(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cwd = Path(tmp_dir)
            project_cfg = _ProjectConfig(
                path=str(cwd / "project"),
                agents={"codex": AgentConfig(shares=["data"])},
            )
            parsed = ParsedArgs(False, "", "codex", [], False, [])
            context = ConfigContext(
                store=mock.Mock(),
                project_cfg=project_cfg,
                agents={},
                bases={},
                extensions={},
            )

            with mock.patch(
                "aicage.runtime.docker_args.resolvers.shares.Path.cwd", return_value=cwd
            ):
                resolved = shares.resolve(context, "codex", parsed)

        expected_path = (cwd / "data").resolve()
        self.assertEqual(
            ResolvedArgs(
                mounts=[MountRequest(host_path=expected_path, read_only=False)]
            ),
            resolved,
        )

    def test_resolve_returns_share_mounts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cwd = Path(tmp_dir)
            parsed = ParsedArgs(False, "", "codex", [], False, ["data:ro"])
            context = ConfigContext(
                store=mock.Mock(),
                project_cfg=_ProjectConfig(path=str(cwd / "project"), agents={}),
                agents={},
                bases={},
                extensions={},
            )

            with mock.patch(
                "aicage.runtime.docker_args.resolvers.shares.Path.cwd", return_value=cwd
            ):
                resolved = shares.resolve(context, "codex", parsed)

        expected_path = (cwd / "data").resolve()
        self.assertEqual(
            ResolvedArgs(
                mounts=[MountRequest(host_path=expected_path, read_only=True)]
            ),
            resolved,
        )

    def test_resolve_includes_approved_extension_shares(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cwd = Path(tmp_dir)
            project_cfg = _ProjectConfig(
                path=str(cwd / "project"),
                agents={
                    "codex": AgentConfig(
                        extensions=["gh"], extension_mounts={"gh": True}
                    )
                },
            )
            parsed = ParsedArgs(False, "", "codex", [], False, ["data"])
            context = ConfigContext(
                store=mock.Mock(),
                project_cfg=project_cfg,
                agents={},
                bases={},
                extensions={
                    "gh": ExtensionMetadata(
                        extension_id="gh",
                        name="GitHub CLI",
                        description="Desc",
                        shares=["~/.config/gh", "data"],
                        directory=Path("/test-tmp/ext"),
                        scripts_dir=Path("/test-tmp/ext/scripts"),
                        dockerfile_path=None,
                    )
                },
            )

            with mock.patch(
                "aicage.runtime.docker_args.resolvers.shares.Path.cwd", return_value=cwd
            ):
                resolved = shares.resolve(context, "codex", parsed)

        expected_paths = [
            (cwd / "data").resolve(),
            Path.home().resolve() / ".config" / "gh",
        ]
        self.assertEqual(
            ResolvedArgs(
                mounts=[
                    MountRequest(host_path=path, read_only=False)
                    for path in expected_paths
                ]
            ),
            resolved,
        )

    def test_resolve_skips_unapproved_extension_shares(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cwd = Path(tmp_dir)
            project_cfg = _ProjectConfig(
                path=str(cwd / "project"),
                agents={
                    "codex": AgentConfig(
                        extensions=["gh"], extension_mounts={"gh": False}
                    )
                },
            )
            parsed = ParsedArgs(False, "", "codex", [], False, [])
            context = ConfigContext(
                store=mock.Mock(),
                project_cfg=project_cfg,
                agents={},
                bases={},
                extensions={
                    "gh": ExtensionMetadata(
                        extension_id="gh",
                        name="GitHub CLI",
                        description="Desc",
                        shares=["~/.config/gh"],
                        directory=Path("/test-tmp/ext"),
                        scripts_dir=Path("/test-tmp/ext/scripts"),
                        dockerfile_path=None,
                    )
                },
            )

            with mock.patch(
                "aicage.runtime.docker_args.resolvers.shares.Path.cwd", return_value=cwd
            ):
                resolved = shares.resolve(context, "codex", parsed)

        self.assertEqual(ResolvedArgs(), resolved)

    def test_resolve_skips_missing_extension_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cwd = Path(tmp_dir)
            project_cfg = _ProjectConfig(
                path=str(cwd / "project"),
                agents={
                    "codex": AgentConfig(
                        extensions=["gh"], extension_mounts={"gh": True}
                    )
                },
            )
            parsed = ParsedArgs(False, "", "codex", [], False, [])
            context = ConfigContext(
                store=mock.Mock(),
                project_cfg=project_cfg,
                agents={},
                bases={},
                extensions={},
            )

            with mock.patch(
                "aicage.runtime.docker_args.resolvers.shares.Path.cwd", return_value=cwd
            ):
                resolved = shares.resolve(context, "codex", parsed)

        self.assertEqual(ResolvedArgs(), resolved)
