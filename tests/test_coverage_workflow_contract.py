"""Keep pull-request coverage separate from main's CodeScene publisher."""

from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(
    encoding="utf-8"
)
MAIN_COVERAGE_WORKFLOW = (
    REPOSITORY_ROOT / ".github" / "workflows" / "coverage-main.yml"
).read_text(encoding="utf-8")
GENERATE_COVERAGE_ACTION = (
    "leynos/shared-actions/.github/actions/generate-coverage"
    "@152d9c4784d0ae5877938a984fe6d1f04d718fd8"
)
UPLOAD_CODESCENE_ACTION = (
    "leynos/shared-actions/.github/actions/upload-codescene-coverage"
    "@152d9c4784d0ae5877938a984fe6d1f04d718fd8"
)


def test_pull_request_coverage_uses_the_local_ratchet_only() -> None:
    """Keep pull-request coverage serial, local, and independent of CodeScene."""
    assert "pull_request:" in CI_WORKFLOW
    assert "if: github.event_name == 'pull_request'" in CI_WORKFLOW
    assert GENERATE_COVERAGE_ACTION in CI_WORKFLOW
    assert "python-source: ./claude_q" in CI_WORKFLOW
    assert "baseline-python-file: .coverage-baseline.python" in CI_WORKFLOW
    assert "pytest-workers: ''" in CI_WORKFLOW
    assert "with-ratchet: 'true'" in CI_WORKFLOW
    assert "CS_ACCESS_TOKEN" not in CI_WORKFLOW
    assert "codescene" not in CI_WORKFLOW.casefold()
    assert "fetch-depth: 0" not in CI_WORKFLOW


def test_main_coverage_publishes_the_ratchet_to_codescene() -> None:
    """Keep CodeScene publication restricted to pushes to main."""
    assert "push:\n    branches: [main]" in MAIN_COVERAGE_WORKFLOW
    assert "pull_request:" not in MAIN_COVERAGE_WORKFLOW
    assert "CS_ACCESS_TOKEN" in MAIN_COVERAGE_WORKFLOW
    assert GENERATE_COVERAGE_ACTION in MAIN_COVERAGE_WORKFLOW
    assert "python-source: ./claude_q" in MAIN_COVERAGE_WORKFLOW
    assert "baseline-python-file: .coverage-baseline.python" in MAIN_COVERAGE_WORKFLOW
    assert "pytest-workers: ''" in MAIN_COVERAGE_WORKFLOW
    assert "with-ratchet: 'true'" in MAIN_COVERAGE_WORKFLOW
    assert UPLOAD_CODESCENE_ACTION in MAIN_COVERAGE_WORKFLOW
    assert "mode: upload" in MAIN_COVERAGE_WORKFLOW
