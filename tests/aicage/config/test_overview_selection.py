from pathlib import Path
from unittest import TestCase, mock

from aicage.cli_types import ParsedArgs
from aicage.config import overview_selection
from aicage.config.agent.models import AgentMetadata
from aicage.config.base.models import BaseMetadata
from aicage.config.context import ConfigContext
from aicage.config.extensions.loader import ExtensionMetadata
from aicage.config.image_refs import default_extended_image_ref
from aicage.config.project_config import AgentConfig, _ProjectConfig
from aicage.config.run_config_draft import _create_run_config_draft


class OverviewSelectionTests(TestCase):
    def test_resolve_overview_selection_returns_agent_image_ref_without_extensions(
        self,
    ) -> None:
        draft = _create_run_config_draft(
            Path("/repo"),
            "codex",
            _ProjectConfig(path="/repo", agents={"codex": AgentConfig(base="ubuntu")}),
            ParsedArgs(False, "", "codex", [], False, []),
        )
        context = ConfigContext(
            store=mock.Mock(),
            project_cfg=draft.project_cfg,
            agents={
                "codex": AgentMetadata(
                    agent_path_files=[],
                    agent_path_directories=[],
                    agent_full_name="Codex CLI",
                    agent_homepage="https://example.com",
                    build_local=False,
                    valid_bases={"ubuntu": "repo:ubuntu"},
                    local_definition_dir=Path("/test-tmp/agent"),
                )
            },
            bases={
                "ubuntu": BaseMetadata(
                    from_image="ubuntu:latest",
                    base_image_distro="Ubuntu",
                    base_image_description="Default",
                    architectures=["amd64", "arm64"],
                    build_local=False,
                    local_definition_dir=Path("/test-tmp/base"),
                )
            },
            extensions={},
        )

        with mock.patch(
            "aicage.config.overview_selection.agent_image_ref",
            return_value="repo:ubuntu",
        ):
            selection = overview_selection.resolve_overview_selection(draft, context)

        self.assertEqual("ubuntu", selection.base)
        self.assertEqual("repo:ubuntu", selection.image_ref)

    def test_resolve_overview_selection_uses_grouped_extensions_for_default_image_ref(
        self,
    ) -> None:
        draft = _create_run_config_draft(
            Path("/repo"),
            "codex",
            _ProjectConfig(
                path="/repo",
                agents={
                    "codex": AgentConfig(
                        base="ubuntu",
                        image_ref="aicage-extended:codex-ubuntu-zeta-alpha",
                        extensions=["zeta", "alpha"],
                    )
                },
            ),
            ParsedArgs(False, "", "codex", [], False, []),
        )
        context = ConfigContext(
            store=mock.Mock(),
            project_cfg=draft.project_cfg,
            agents={
                "codex": AgentMetadata(
                    agent_path_files=[],
                    agent_path_directories=[],
                    agent_full_name="Codex CLI",
                    agent_homepage="https://example.com",
                    build_local=False,
                    valid_bases={"ubuntu": "repo:ubuntu"},
                    local_definition_dir=Path("/test-tmp/agent"),
                )
            },
            bases={
                "ubuntu": BaseMetadata(
                    from_image="ubuntu:latest",
                    base_image_distro="Ubuntu",
                    base_image_description="Default",
                    architectures=["amd64", "arm64"],
                    build_local=False,
                    local_definition_dir=Path("/test-tmp/base"),
                )
            },
            extensions={
                "alpha": _extension("alpha"),
                "zeta": _extension("zeta", dockerfile=True),
            },
        )

        with (
            mock.patch("aicage.config.overview_selection.write_extended_image_config"),
            mock.patch(
                "aicage.config.overview_selection.agent_image_ref",
                return_value="repo:ubuntu",
            ),
        ):
            selection = overview_selection.resolve_overview_selection(draft, context)

        self.assertEqual(
            default_extended_image_ref(
                "codex",
                "ubuntu",
                ["zeta", "alpha"],
                context.extensions,
            ),
            selection.image_ref,
        )
        self.assertEqual(selection.image_ref, draft.agent_cfg.image_ref)


def _extension(extension_id: str, dockerfile: bool = False) -> ExtensionMetadata:
    base_dir = Path("/test-tmp") / extension_id
    return ExtensionMetadata(
        extension_id=extension_id,
        name=extension_id,
        description="desc",
        shares=[],
        directory=base_dir,
        scripts_dir=base_dir / "scripts",
        dockerfile_path=base_dir / "Dockerfile" if dockerfile else None,
    )
