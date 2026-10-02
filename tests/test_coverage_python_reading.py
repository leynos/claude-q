"""Contract reader: how the coverage contract reads its inputs and refuses bad ones.

Companion to ``test_coverage_python_version.py``, which applies the resolver to
this repository's lanes. These cases exercise the reading boundary alone: the
``.python-version`` parser, the optional-file read that treats only a missing
file as absent, the strict workflow loader, and the ``requires-python`` and
version parsing, each failing with the typed contract error.
"""

from __future__ import annotations

import typing as typ

import pytest
from coverage_python_sources import (
    SETUP_PYTHON,
    CoverageContractError,
    coverage_calls,
    python_version_entry,
    read_required_text,
    read_text_if_present,
    rejected_versions,
    requires_python,
)
from packaging.specifiers import SpecifierSet

if typ.TYPE_CHECKING:
    from pathlib import Path

#: Minimal steps for the malformed-workflow fixtures below.
SETUP: typ.Final[dict[str, object]] = {"uses": f"{SETUP_PYTHON}{'0' * 40}"}
COVERAGE: typ.Final[dict[str, object]] = {
    "uses": f"leynos/shared-actions/.github/actions/generate-coverage@{'0' * 40}"
}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (None, ""),
        ("", ""),
        ("3.13\n", "3.13"),
        ("# pinned\n\n  3.13  \n3.12\n", "3.13"),
        ("# comments only\n", ""),
    ],
    ids=["absent", "empty", "one-entry", "first-entry-after-comments", "comments-only"],
)
def test_the_python_version_entry_is_the_first_non_comment_line(
    text: str | None, expected: str
) -> None:
    """Parsing is pure: the first non-comment entry, or nothing."""
    assert python_version_entry(text) == expected, f"{text!r} should read {expected!r}"


def test_a_python_version_file_is_read_from_the_tree(tmp_path: Path) -> None:
    """A real ``.python-version`` feeds the parser; a missing one reads as absent."""
    present = tmp_path / ".python-version"
    present.write_text("# pinned\n3.12\n", encoding="utf-8")

    assert python_version_entry(read_text_if_present(present)) == "3.12", (
        "a present file is read and parsed"
    )
    assert read_text_if_present(tmp_path / "missing" / ".python-version") is None, (
        "a missing file reads as absent, not as empty text"
    )


@pytest.mark.parametrize(
    "workflow",
    [
        "- a list\n",
        "jobs: scalar\n",
        "jobs:\n  cov: scalar\n",
        "jobs:\n  cov: [x]\n",
        "jobs: [unclosed\n",
        "jobs:\n",
        "jobs:\n  cov:\n",
        "jobs:\n  cov:\n    steps: []\n    steps: []\n",
        "",
        "jobs:\n  broken:\n  cov:\n    steps: []\n",
        "jobs:\n  cov:\n    steps: scalar\n",
        "jobs:\n  cov:\n    steps:\n",
        "jobs:\n  cov:\n    steps: [x]\n",
        (
            "jobs:\n  cov:\n    steps:\n"
            f"      - uses: {COVERAGE['uses']}\n"
            "        with: scalar\n"
        ),
        (
            "jobs:\n  cov:\n    steps:\n"
            f"      - uses: {COVERAGE['uses']}\n"
            "        env: scalar\n"
        ),
        (f"jobs:\n  cov:\n    env:\n    steps:\n      - uses: {COVERAGE['uses']}\n"),
        (
            "jobs:\n  cov:\n    steps:\n"
            f"      - uses: {SETUP['uses']}\n"
            "        with: scalar\n"
        ),
    ],
    ids=[
        "list-top-level",
        "scalar-jobs",
        "scalar-job",
        "list-job",
        "not-yaml",
        "null-jobs",
        "null-job",
        "duplicate-steps",
        "empty",
        "null-job-beside-a-valid-one",
        "scalar-steps",
        "null-steps",
        "scalar-step-item",
        "scalar-coverage-with",
        "scalar-coverage-env",
        "null-job-env",
        "scalar-setup-with",
    ],
)
def test_a_wrongly_shaped_workflow_is_refused(workflow: str) -> None:
    """A workflow, jobs mapping or job of the wrong shape fails, not reads empty."""
    with pytest.raises(CoverageContractError):
        coverage_calls(workflow)


@pytest.mark.parametrize(
    "workflow",
    ["on: push\n", "jobs: {}\n"],
    ids=["no-jobs-key", "empty-jobs"],
)
def test_a_workflow_without_jobs_has_no_calls(workflow: str) -> None:
    """An absent jobs key or an empty jobs mapping holds no call, and is no error."""
    assert coverage_calls(workflow) == [], f"{workflow!r} should hold no calls"


@pytest.mark.parametrize(
    ("kind", "cause"),
    [("missing", FileNotFoundError), ("undecodable", UnicodeDecodeError)],
    ids=["missing", "undecodable"],
)
def test_a_required_file_that_cannot_be_read_fails_loudly(
    tmp_path: Path, kind: str, cause: type[Exception]
) -> None:
    """A file the contract needs raises a typed error naming it, with its cause."""
    path = tmp_path / f"{kind}.yml"
    if kind == "undecodable":
        path.write_bytes(b"\xff\xfe")

    with pytest.raises(CoverageContractError, match=kind) as raised:
        read_required_text(path)

    assert isinstance(raised.value.__cause__, cause), (
        f"{kind} should chain {cause.__name__}, got {raised.value.__cause__!r}"
    )


@pytest.mark.parametrize(
    ("kind", "cause"),
    [("undecodable", UnicodeDecodeError), ("directory", OSError)],
    ids=["undecodable", "directory"],
)
def test_an_optional_file_that_cannot_be_read_fails_loudly(
    tmp_path: Path, kind: str, cause: type[Exception]
) -> None:
    """Only absence reads as absent; a directory or undecodable file raises.

    The typed error names the path and keeps the original failure as its cause.
    """
    path = tmp_path / kind
    if kind == "directory":
        path.mkdir()
    else:
        path.write_bytes(b"\xff\xfe")

    with pytest.raises(CoverageContractError, match=kind) as raised:
        read_text_if_present(path)

    assert isinstance(raised.value.__cause__, cause), (
        f"{kind} should chain {cause.__name__}, got {raised.value.__cause__!r}"
    )


@pytest.mark.parametrize(
    "pyproject",
    [
        "not = [valid toml",
        "[tool.x]\nname = 1\n",
        "[project]\nname = 'x'\n",
        "[project]\nrequires-python = 3\n",
        "[project]\nrequires-python = []\n",
        "[project]\nrequires-python = {}\n",
        "[project]\nrequires-python = 'not a specifier'\n",
    ],
    ids=[
        "not-toml",
        "no-project",
        "no-requires-python",
        "not-a-string",
        "empty-array",
        "empty-table",
        "bad-specifier",
    ],
)
def test_a_pyproject_without_a_usable_requires_python_is_refused(
    pyproject: str,
) -> None:
    """A missing or malformed ``requires-python`` fails with the typed error."""
    with pytest.raises(CoverageContractError):
        requires_python(pyproject)


def test_a_version_that_does_not_parse_is_refused() -> None:
    """A requested version that is not a version fails with the typed error."""
    with pytest.raises(CoverageContractError):
        rejected_versions(SpecifierSet(">=3.12"), ["three.thirteen"])


@pytest.mark.parametrize(
    ("requires", "accepted", "refused"),
    [
        (">=3.13", ["3.13", "3.14", "3.15"], ["3.9", "3.10", "3.12"]),
        (">=3.12,<3.14", ["3.12", "3.13"], ["3.11", "3.14"]),
        ("==3.13.*", ["3.13"], ["3.12", "3.14"]),
    ],
    ids=["lower-bound", "bounded-range", "pinned-minor"],
)
def test_requires_python_is_read_from_the_project_and_compared_by_version(
    requires: str, accepted: list[str], refused: list[str]
) -> None:
    """The specifier comes from the supplied pyproject, and ``3.9`` is below ``3.13``.

    A textual comparison would rank ``3.9`` above ``3.13``, so the cases pair
    two-digit and one-digit minors across each boundary.
    """
    specifier = requires_python(f'[project]\nrequires-python = "{requires}"\n')

    assert rejected_versions(specifier, accepted) == [], f"{accepted} under {requires}"
    assert rejected_versions(specifier, refused) == refused, (
        f"{refused} should all fall outside {requires}"
    )
