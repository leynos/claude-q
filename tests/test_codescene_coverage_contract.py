"""Hold the CV-005 coverage shape, and prove each clause by mutation.

The first test judges this repository's workflows. Every other test mutates a
copy of them in the way a later edit could, and asserts that the clause meant
to catch that edit does. A clause no mutation fails is indistinguishable from
a clause that was never written, so each rule in `codescene_contract_rules`
has at least one case here that only it refuses.
"""

from __future__ import annotations

import copy
import typing as typ
from pathlib import Path

import pytest
from codescene_contract_rules import (
    Document,
    WorkflowError,
    coverage_violations,
    load_workflow,
    publisher_violations,
    pull_request_closure,
    pull_request_contacts,
    read_workflows,
    retired_names,
    upload_steps,
)

if typ.TYPE_CHECKING:
    import collections.abc as cabc

type Documents = dict[str, Document]
type Rule = cabc.Callable[[Documents], list[str]]

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
RULES: tuple[Rule, ...] = (
    pull_request_contacts,
    publisher_violations,
    coverage_violations,
    retired_names,
)
PROBE = "probe.yml"
CREDENTIAL_REFERENCE = "${{ secrets.CS_ACCESS_TOKEN }}"
UPLOADER = "leynos/shared-actions/.github/actions/upload-codescene-coverage"
DISPATCH = "github.event_name == 'workflow_dispatch'"
MAIN_GUARD = "env.CS_ACCESS_TOKEN != '' && github.ref == 'refs/heads/main'"


@pytest.fixture(scope="module")
def repository() -> Documents:
    """Read this repository's workflows once."""
    return read_workflows(WORKFLOWS)


@pytest.fixture
def documents(repository: Documents) -> Documents:
    """Give each test its own copy to mutate."""
    return copy.deepcopy(repository)


def _violations(documents: Documents) -> list[str]:
    """Return every rule's violations over some documents."""
    return [problem for rule in RULES for problem in rule(documents)]


def _publisher(documents: Documents) -> tuple[Document, dict[str, object]]:
    """Return the publisher document and its upload step."""
    [(name, step)] = upload_steps(documents)
    return documents[name], step


def _first_job(document: Document) -> dict[str, object]:
    """Return a workflow's first job."""
    jobs = typ.cast("dict[str, dict[str, object]]", document["jobs"])
    return next(iter(jobs.values()))


def _steps(document: Document) -> list[dict[str, object]]:
    """Return a workflow's first job's steps."""
    return typ.cast("list[dict[str, object]]", _first_job(document)["steps"])


def _add_step(documents: Documents, step: dict[str, object]) -> None:
    """Append a step to the pull-request lane."""
    _steps(documents["ci.yml"]).append(step)


def _coverage_step(document: Document) -> dict[str, object]:
    """Return a workflow's generate-coverage step."""
    return next(
        s for s in _steps(document) if "generate-coverage" in str(s.get("uses"))
    )


def test_repository_workflows_satisfy_the_contract(documents: Documents) -> None:
    """Hold every clause over the workflows as committed."""
    assert _violations(documents) == []


def _probe(uses_prefix: str = "./") -> tuple[Document, Document]:
    """Return a pull-request caller job and a callee reaching CodeScene.

    The callee declares only `workflow_call`, so it serves no pull request by
    its own trigger, and receives the token through `secrets: inherit`.
    """
    callee = load_workflow(
        PROBE,
        "on:\n  workflow_call:\njobs:\n  leak:\n    runs-on: ubuntu-latest\n"
        '    steps:\n      - run: curl -H "$T" https://api.codescene.io/v2\n'
        f"        env:\n          T: '{CREDENTIAL_REFERENCE}'\n",
    )
    caller = {"uses": f"{uses_prefix}.github/workflows/{PROBE}", "secrets": "inherit"}
    return caller, callee


@pytest.mark.parametrize("prefix", ["./", "$/"])
def test_closure_follows_a_called_workflow(documents: Documents, prefix: str) -> None:
    """A workflow_call callee of a pull-request job is judged as a PR lane."""
    caller, callee = _probe(prefix)
    documents[PROBE] = callee
    typ.cast("dict[str, object]", documents["ci.yml"]["jobs"])["probe"] = caller
    assert PROBE in pull_request_closure(documents)
    found = pull_request_contacts(documents)
    assert f"{PROBE} names the CodeScene host" in found
    assert f"{PROBE} puts CS_ACCESS_TOKEN in reach" in found
    assert "ci.yml job probe forwards every secret with `secrets: inherit`" in found


def test_closure_follows_a_workflow_run_chain(documents: Documents) -> None:
    """A workflow_run chained onto a pull-request workflow is a PR lane."""
    _, callee = _probe()
    lane = str(documents["ci.yml"].get("name", "ci.yml"))
    callee[True] = {"workflow_run": {"workflows": [lane]}}
    documents[PROBE] = callee
    assert f"{PROBE} names the CodeScene host" in pull_request_contacts(documents)


@pytest.mark.parametrize(
    ("uses", "reason"),
    [
        ("$/.github/workflows/ci.yml@main", "a `\\$/` call cannot name a ref"),
        (
            "leynos/claude-q/.github/workflows/ci.yml@main",
            "runs this repository's workflow at a ref",
        ),
        ("./.github/workflows/missing.yml", "names no workflow in this repository"),
    ],
)
def test_closure_refuses_calls_it_cannot_read(
    documents: Documents, uses: str, reason: str
) -> None:
    """A call the closure cannot follow to a checked-out file is refused."""
    jobs = typ.cast("dict[str, object]", documents["ci.yml"]["jobs"])
    jobs["probe"] = {"uses": uses}
    with pytest.raises(WorkflowError, match=reason):
        pull_request_closure(documents)


def test_closure_starts_from_pull_request_target(documents: Documents) -> None:
    """A pull_request_target workflow runs with secrets on every PR event."""
    documents[PROBE] = load_workflow(
        PROBE,
        "on: pull_request_target\njobs:\n  a:\n    steps:\n"
        "      - run: curl https://codescene.io\n",
    )
    assert f"{PROBE} names the CodeScene host" in pull_request_contacts(documents)


def test_callee_secret_declaration_is_refused(documents: Documents) -> None:
    """A called workflow declaring the secret by name is refused.

    The declaration is a mapping key with no reference in any value, so only
    a reading of keys as well as values sees it.
    """
    documents[PROBE] = load_workflow(
        PROBE,
        "on:\n  workflow_call:\n    secrets:\n      CS_ACCESS_TOKEN:\n"
        "        required: false\njobs: {}\n",
    )
    jobs = typ.cast("dict[str, object]", documents["ci.yml"]["jobs"])
    jobs["probe"] = {"uses": f"./.github/workflows/{PROBE}"}
    assert f"{PROBE} puts CS_ACCESS_TOKEN in reach" in pull_request_contacts(documents)


@pytest.mark.parametrize(
    ("step", "reason"),
    [
        ({"run": f"echo {CREDENTIAL_REFERENCE}"}, "puts CS_ACCESS_TOKEN in reach"),
        (
            {"uses": "x/y@v1", "with": {"t": CREDENTIAL_REFERENCE}},
            "puts CS_ACCESS_TOKEN in reach",
        ),
        (
            {"run": "true", "env": {"OTHER": CREDENTIAL_REFERENCE}},
            "puts CS_ACCESS_TOKEN in reach",
        ),
        ({"run": "echo '${{ toJSON( secrets ) }}'"}, "serializes the secrets context"),
        ({"run": "echo ${{ secrets['CS_' + 'X'] }}"}, "indexes the secrets context"),
        ({"run": "curl https://API.CODESCENE.IO"}, "names the CodeScene host"),
        ({"run": "cs-coverage check coverage.xml"}, "names the cs-coverage client"),
        (
            {"uses": f"{UPLOADER}@x"},
            "calls the CodeScene uploader",
        ),
    ],
)
def test_pull_request_lane_cannot_reach_codescene(
    documents: Documents, step: dict[str, object], reason: str
) -> None:
    """Every route to CodeScene or its token from a PR step is refused."""
    _add_step(documents, step)
    assert f"ci.yml {reason}" in pull_request_contacts(documents)


def test_token_in_workflow_env_is_refused(documents: Documents) -> None:
    """A workflow-level env reaches every step of every job."""
    documents["ci.yml"]["env"] = {"CS_ACCESS_TOKEN": CREDENTIAL_REFERENCE}
    assert "ci.yml puts CS_ACCESS_TOKEN in reach" in pull_request_contacts(documents)


def test_host_in_workflow_defaults_is_refused(documents: Documents) -> None:
    """A default shell runs before every step, naming no step at all."""
    documents["ci.yml"]["defaults"] = {
        "run": {"shell": "curl -s https://Api.CodeScene.io >/dev/null; bash {0}"}
    }
    assert "ci.yml names the CodeScene host" in pull_request_contacts(documents)


def test_duplicate_keys_are_refused() -> None:
    """PyYAML would keep the second `runs-on` and discard the first."""
    text = "on: push\njobs:\n  a:\n    runs-on: x\n    runs-on: y\n    steps: []\n"
    with pytest.raises(WorkflowError, match="duplicate key 'runs-on'"):
        load_workflow("dup.yml", text)


@pytest.mark.parametrize(
    "trigger",
    ["on: pull_request", "on: [push, pull_request]", "'on': {pull_request: {}}"],
)
def test_every_trigger_form_is_read(documents: Documents, trigger: str) -> None:
    """Scalar, sequence and quoted-key mapping triggers all serve PRs."""
    documents[PROBE] = load_workflow(
        PROBE, f"{trigger}\njobs:\n  a:\n    steps:\n      - run: cs-coverage check\n"
    )
    assert f"{PROBE} names the cs-coverage client" in pull_request_contacts(documents)


def test_both_trigger_spellings_are_refused() -> None:
    """GitHub merges `on` and `'on'`; a reader of either is blind to the other."""
    text = "on: push\n'on': pull_request\njobs: {}\n"
    with pytest.raises(WorkflowError, match="declares `on` 2 times"):
        pull_request_closure({"both.yml": load_workflow("both.yml", text)})


@pytest.mark.parametrize(
    "guard",
    [
        "env.CS_ACCESS_TOKEN != ''",
        "github.ref == 'refs/heads/main'",
        f"{MAIN_GUARD} || {DISPATCH}",
        # The discriminating case: both required conjuncts stay whole and the
        # `||` hides inside an extra one. Exact conjunct equality refuses it,
        # which is why this contract needs no separate `||` scan.
        f"{MAIN_GUARD} && github.actor != 'x' || {DISPATCH}",
        f"{MAIN_GUARD} && false",
    ],
)
def test_upload_guard_is_exactly_token_and_main(
    documents: Documents, guard: str
) -> None:
    """The upload runs only with the token, and only for main."""
    _, upload = _publisher(documents)
    upload["if"] = guard
    assert any("upload must be guarded" in p for p in publisher_violations(documents))


def test_upload_guard_accepts_the_expression_wrapper(documents: Documents) -> None:
    """`${{ }}` around the condition is the same condition."""
    _, upload = _publisher(documents)
    upload["if"] = "${{ github.ref == 'refs/heads/main' && env.CS_ACCESS_TOKEN != '' }}"
    assert publisher_violations(documents) == []


@pytest.mark.parametrize(
    ("concurrency", "expected"),
    [
        ({"group": "coverage-main", "cancel-in-progress": True}, "cancels"),
        ({"group": "coverage-main", "cancel-in-progress": "${{ true }}"}, "cancels"),
        (None, "needs a workflow-level concurrency group"),
    ],
)
def test_publisher_never_cancels(
    documents: Documents, concurrency: object, expected: str
) -> None:
    """A cancelled publisher abandons its upload and its baseline write."""
    publisher, _ = _publisher(documents)
    publisher["concurrency"] = concurrency
    assert any(expected in p for p in publisher_violations(documents))


def test_publisher_job_cannot_cancel(documents: Documents) -> None:
    """A job-level concurrency block cancels just as well."""
    publisher, _ = _publisher(documents)
    _first_job(publisher)["concurrency"] = {"group": "g", "cancel-in-progress": True}
    assert any("cancels" in p for p in publisher_violations(documents))


@pytest.mark.parametrize(
    "on",
    [
        {"push": {"branches": ["main"]}, "pull_request": None},
        {"push": {"branches": ["**"]}},
        {"push": {"tags": ["v*"]}},
        {"workflow_dispatch": None},
    ],
)
def test_publisher_answers_only_a_push_to_main(
    documents: Documents, on: object
) -> None:
    """Only main's pushes may write the baseline CodeScene is given."""
    publisher, _ = _publisher(documents)
    publisher[True] = on
    assert any("must" in p for p in publisher_violations(documents))


def test_publisher_job_runs_unconditionally(documents: Documents) -> None:
    """A job-level `if: false` skips the upload with every step intact."""
    publisher, _ = _publisher(documents)
    _first_job(publisher)["if"] = "false"
    assert any("must run unconditionally" in p for p in publisher_violations(documents))


def test_token_binding_is_asserted_positively(documents: Documents) -> None:
    """Deleting the binding makes the guard false, and the upload skips forever."""
    _, upload = _publisher(documents)
    del upload["env"]
    assert any("must bind" in p for p in publisher_violations(documents))


def test_token_binding_cannot_move_to_the_job(documents: Documents) -> None:
    """A binding in a wider scope reaches every step of the job."""
    publisher, upload = _publisher(documents)
    upload["env"] = {}
    _first_job(publisher)["env"] = {"CS_ACCESS_TOKEN": CREDENTIAL_REFERENCE}
    found = publisher_violations(documents)
    assert any("must bind" in p for p in found)
    assert any("outside the upload step" in p for p in found)


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("access-token", "${{ secrets.OTHER }}", "must pass access-token"),
        ("mode", "check", "must name `mode: upload`"),
    ],
)
def test_upload_inputs_are_asserted(
    documents: Documents, key: str, value: str, expected: str
) -> None:
    """The upload passes the bound token, and says it uploads."""
    _, upload = _publisher(documents)
    typ.cast("dict[str, object]", upload["with"])[key] = value
    assert any(expected in p for p in publisher_violations(documents))


def test_second_uploader_is_refused(documents: Documents) -> None:
    """A second uploader could publish where nothing here looks."""
    publisher, upload = _publisher(documents)
    _steps(publisher).append(copy.deepcopy(upload))
    assert publisher_violations(documents) == [
        "expected one CodeScene upload step, found 2"
    ]


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("with-ratchet", "false", "with-ratchet 'true'"),
        ("publish-artefact", "true", "publish-artefact 'false'"),
        ("python-source", "./tests", "selection differs"),
    ],
)
def test_pull_request_coverage_ratchets_like_main(
    documents: Documents, key: str, value: str, expected: str
) -> None:
    """The PR lane ratchets against main's baseline and publishes nothing."""
    typ.cast("dict[str, object]", _coverage_step(documents["ci.yml"])["with"])[key] = (
        value
    )
    assert any(expected in p for p in coverage_violations(documents))


def test_pull_request_coverage_cannot_be_switched_off(documents: Documents) -> None:
    """`if: false` keeps the step while the ratchet never runs."""
    _coverage_step(documents["ci.yml"])["if"] = "false"
    assert any("may run only as" in p for p in coverage_violations(documents))


def test_pull_request_coverage_must_exist(documents: Documents) -> None:
    """Deleting the PR coverage step deletes the ratchet."""
    steps = _steps(documents["ci.yml"])
    steps.remove(_coverage_step(documents["ci.yml"]))
    assert "no pull-request lane generates coverage for the ratchet" in (
        coverage_violations(documents)
    )


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"if": "false"}, "must run unconditionally"),
        (
            {"uses": "leynos/shared-actions/.github/actions/generate-coverage@main"},
            "full SHA",
        ),
    ],
)
def test_publisher_coverage_is_pinned_and_unconditional(
    documents: Documents, change: dict[str, object], expected: str
) -> None:
    """The baseline writer always runs, at the uploader's full-SHA pin."""
    publisher, _ = _publisher(documents)
    _coverage_step(publisher).update(change)
    assert any(expected in p for p in coverage_violations(documents))


def _restore_refresher(documents: Documents) -> None:
    """Bring back the workflow that refreshed the installer checksum."""
    documents["get-codescene-sha.yml"] = {True: "workflow_dispatch", "jobs": {}}


def _restore_installer_checksum(documents: Documents) -> None:
    """Pass the uploader the input it now rejects."""
    _, upload = _publisher(documents)
    typ.cast("dict[str, object]", upload["with"])["installer-checksum"] = "abc"


def _restore_variable(documents: Documents) -> None:
    """Read the retired checksum variable into a lane."""
    documents["ci.yml"]["env"] = {"CODESCENE_CLI_SHA256": "${{ vars.X }}"}


@pytest.mark.parametrize(
    "mutation",
    [_restore_refresher, _restore_installer_checksum, _restore_variable],
)
def test_retired_checksum_machinery_stays_gone(
    documents: Documents, mutation: cabc.Callable[[Documents], None]
) -> None:
    """The retired installer checksum is refused wherever it reappears."""
    mutation(documents)
    assert retired_names(documents) != []


def test_reader_refuses_an_empty_directory(tmp_path: Path) -> None:
    """Finding no workflow is the reader failing, not the repository passing."""
    with pytest.raises(WorkflowError, match="no workflows were read"):
        read_workflows(tmp_path)


def test_reader_reads_every_suffix_and_case(tmp_path: Path) -> None:
    """GitHub runs `.yaml` and upper-case suffixes too."""
    for name in ("a.YML", "b.yaml"):
        (tmp_path / name).write_text("on: push\njobs: {}\n", encoding="utf-8")
    assert sorted(read_workflows(tmp_path)) == ["a.YML", "b.yaml"]


def test_reader_names_the_file_for_invalid_yaml() -> None:
    """A parser error must say which workflow it came from."""
    with pytest.raises(WorkflowError, match=r"^bad\.yml: not valid YAML"):
        load_workflow("bad.yml", "jobs: [\n")
