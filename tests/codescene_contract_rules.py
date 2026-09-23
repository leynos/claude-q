"""Read the workflows and judge them against CV-005.

CV-005 moves every CodeScene call off the pull-request lanes. A pull request
generates coverage for its own ratchet and nothing else, and one workflow,
answering only a push to main, uploads. The reason is the call rather than the
artefact: the shared uploader pins the cs-coverage archive by digest, but the
tool talks to CodeScene's API and refuses to run when that answer changes
shape, which has happened twice. Keeping the call on the trunk keeps such a
change off every pull request's critical path.

Every rule here is a pure function from parsed workflow documents to a list of
violations, so `test_codescene_coverage_contract` can drive each one over this
repository's workflows and over mutated copies it must refuse. Only
`read_workflows` touches the disk.

A reading that finds nothing is a fault of the reader, not a pass: every rule
is a refusal, and a refusal over an empty subject set is satisfied by any
repository at all. Those faults raise `WorkflowError` instead of returning.
"""

from __future__ import annotations

import copy
import re
import typing as typ

import yaml

if typ.TYPE_CHECKING:
    import collections.abc as cabc
    from pathlib import Path

type Document = dict[object, object]
type Step = dict[str, object]

#: This repository, for refusing a qualified call to one of its own workflows.
REPOSITORY: typ.Final[str] = "leynos/claude-q"
WORKFLOW_PREFIX: typ.Final[str] = ".github/workflows/"
COVERAGE_ACTION: typ.Final[str] = (
    "leynos/shared-actions/.github/actions/generate-coverage"
)
UPLOAD_ACTION: typ.Final[str] = (
    "leynos/shared-actions/.github/actions/upload-codescene-coverage"
)
PULL_REQUEST_EVENTS: typ.Final[frozenset[str]] = frozenset({
    "pull_request",
    "pull_request_target",
})

#: What no pull-request-reachable scalar may contain, case-folded and with
#: whitespace removed. The token's name catches an `env` key, a reference in a
#: script, an input or an env value under any key, a named `secrets:`
#: forwarding and a `workflow_call` secret declaration alike; indexed and
#: serialized `secrets` reach it without spelling the name.
PULL_REQUEST_FORBIDDEN: typ.Final[tuple[tuple[str, str], ...]] = (
    ("codescene.io", "names the CodeScene host"),
    ("upload-codescene-coverage", "calls the CodeScene uploader"),
    ("cs-coverage", "names the cs-coverage client"),
    ("cs_access_token", "puts CS_ACCESS_TOKEN in reach"),
    ("secrets[", "indexes the secrets context"),
    ("tojson(secrets", "serializes the secrets context"),
)

#: Retired with CV-005 everywhere, not only on pull-request lanes: the
#: uploader rejects `installer-checksum` outright, and the variable and its
#: refresher workflow pinned an installer script the uploader no longer runs.
RETIRED: typ.Final[tuple[str, ...]] = (
    "installer-checksum",
    "codescene_cli_sha256",
    "get-codescene-sha",
)

#: The upload step's whole condition, as a set of conjuncts. Exact rather than
#: a superset: an extra conjunct can only narrow the upload, and `&& false`
#: narrows it to never. Exactness also refuses every `||`, because an `||`
#: leaves some conjunct unequal to both required ones.
UPLOAD_GUARD: typ.Final[frozenset[str]] = frozenset({
    "env.CS_ACCESS_TOKEN != ''",
    "github.ref == 'refs/heads/main'",
})
CREDENTIAL_BINDING: typ.Final[str] = "${{ secrets.CS_ACCESS_TOKEN }}"
CREDENTIAL_INPUT: typ.Final[str] = "${{ env.CS_ACCESS_TOKEN }}"
PULL_REQUEST_GUARD: typ.Final[str] = "github.event_name == 'pull_request'"
PINNED: typ.Final[re.Pattern[str]] = re.compile(r"@[0-9a-f]{40}")


class WorkflowError(ValueError):
    """Raised when the workflows cannot be read as the rules require."""


class _StrictLoader(yaml.SafeLoader):
    """A safe loader that refuses a key declared twice in one mapping.

    PyYAML keeps the last duplicate silently, so a lane declaring `runs-on`
    or `if` twice would be judged on the half GitHub may not use.
    """


def _construct_mapping(loader: _StrictLoader, node: yaml.MappingNode) -> Document:
    """Build a mapping, raising on a repeated key."""
    seen: set[object] = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in seen:
            message = f"duplicate key {key!r} at {key_node.start_mark}"
            raise WorkflowError(message)
        seen.add(key)
    return loader.construct_mapping(node, deep=True)


_StrictLoader.add_constructor(_StrictLoader.DEFAULT_MAPPING_TAG, _construct_mapping)


def load_workflow(name: str, text: str) -> Document:
    r"""Parse one workflow strictly, naming the file on failure.

    Examples
    --------
    >>> load_workflow("ci.yml", "on: push\njobs: {}\n")
    {True: 'push', 'jobs': {}}

    """
    loader = _StrictLoader(text)
    try:
        document = loader.get_single_data()
    except yaml.YAMLError as error:
        message = f"{name}: not valid YAML: {error}"
        raise WorkflowError(message) from error
    except WorkflowError as error:
        message = f"{name}: {error}"
        raise WorkflowError(message) from error
    finally:
        loader.dispose()
    if not isinstance(document, dict):
        message = f"{name}: a workflow must be a mapping"
        raise WorkflowError(message)
    return document


def read_workflows(directory: Path) -> dict[str, Document]:
    """Parse every workflow in a directory, by file name.

    Both suffixes and any case are read, because GitHub runs all of them.
    """
    paths = sorted(
        path
        for path in directory.iterdir()
        if path.suffix.casefold() in {".yml", ".yaml"}
    )
    if not paths:
        message = f"no workflows were read from {directory}"
        raise WorkflowError(message)
    return {
        path.name: load_workflow(path.name, path.read_text(encoding="utf-8"))
        for path in paths
    }


def triggers(name: str, document: Document) -> dict[str, object]:
    """Return a workflow's events in mapping form.

    YAML 1.1 reads a bare `on` as boolean true, and a quoted `'on'` as the
    string. GitHub merges the two, so a workflow declaring both is refused
    rather than read by half.
    """
    spellings = [key for key in ("on", True) if key in document]
    if len(spellings) != 1:
        message = f"{name}: declares `on` {len(spellings)} times, not once"
        raise WorkflowError(message)
    match document[spellings[0]]:
        case str() as event:
            return {event: None}
        case list() as events if all(isinstance(event, str) for event in events):
            return dict.fromkeys(typ.cast("list[str]", events))
        case dict() as events:
            return {str(event): value for event, value in events.items()}
        case other:
            message = f"{name}: cannot read the trigger {other!r}"
            raise WorkflowError(message)


def jobs(name: str, document: Document) -> dict[str, dict[str, object]]:
    """Return a workflow's jobs, refusing a malformed `jobs` block."""
    found = document.get("jobs")
    if not isinstance(found, dict) or not all(
        isinstance(job, dict) for job in found.values()
    ):
        message = f"{name}: `jobs` must map job names to mappings"
        raise WorkflowError(message)
    return typ.cast("dict[str, dict[str, object]]", found)


def steps(name: str, document: Document) -> cabc.Iterator[Step]:
    """Yield every step of every job in one workflow."""
    for job in jobs(name, document).values():
        for step in typ.cast("list[object]", job.get("steps", [])):
            if not isinstance(step, dict):
                message = f"{name}: a step must be a mapping"
                raise WorkflowError(message)
            yield typ.cast("Step", step)


def calls(step: Step, action: str) -> bool:
    """Return whether a step calls one shared action, at any ref."""
    uses = str(step.get("uses", ""))
    return uses.partition("@")[0].casefold() == action.casefold()


def scalars(value: object) -> cabc.Iterator[str]:
    """Yield every key and value in a parsed document as text."""
    match value:
        case dict():
            for key, child in value.items():
                yield str(key)
                yield from scalars(child)
        case list():
            for child in value:
                yield from scalars(child)
        case None:
            return
        case _:
            yield str(value)


def _folded(text: str) -> str:
    """Return text case-folded with all whitespace removed."""
    return re.sub(r"\s+", "", text).casefold()


def local_callee(reference: str, documents: dict[str, Document]) -> str | None:
    """Return the workflow file a job-level `uses:` names in this tree.

    Matched by shape: strip a leading `./` or `$/` and ask whether the rest is
    a file under the workflow directory. A `$/` call carries no ref, and a
    qualified call to this repository runs the file at that ref rather than
    the one checked out, so both are refused rather than followed.
    """
    if reference.casefold().startswith(f"{REPOSITORY}/".casefold()):
        message = f"{reference} runs this repository's workflow at a ref"
        raise WorkflowError(message)
    if reference.startswith("$/") and "@" in reference:
        message = f"{reference}: a `$/` call cannot name a ref"
        raise WorkflowError(message)
    path = reference.removeprefix("./").removeprefix("$/")
    if not path.startswith(WORKFLOW_PREFIX):
        return None
    callee = path.removeprefix(WORKFLOW_PREFIX)
    if callee not in documents:
        message = f"{reference} names no workflow in this repository"
        raise WorkflowError(message)
    return callee


def _callees(name: str, documents: dict[str, Document]) -> set[str]:
    """Return the local workflows one workflow's jobs call."""
    references = (job.get("uses") for job in jobs(name, documents[name]).values())
    return {
        callee
        for reference in references
        if isinstance(reference, str)
        and (callee := local_callee(reference, documents)) is not None
    }


def _chained(found: set[str], documents: dict[str, Document]) -> set[str]:
    """Return workflows a `workflow_run` trigger chains onto any found one."""
    watched_names = {str(documents[name].get("name", name)) for name in found}
    chained: set[str] = set()
    for name, document in documents.items():
        run = triggers(name, document).get("workflow_run")
        watched = run.get("workflows", []) if isinstance(run, dict) else []
        if watched_names.intersection(map(str, typ.cast("list[object]", watched))):
            chained.add(name)
    return chained


def pull_request_closure(documents: dict[str, Document]) -> dict[str, Document]:
    """Return every workflow a pull request can start, directly or not.

    A workflow declaring only `workflow_call` still runs when a pull-request
    job calls it, and `secrets: inherit` hands it the token; a workflow_run
    chained onto a pull-request workflow runs too. So the rules below read the
    transitive closure, not a trigger list.
    """
    found = {
        name
        for name, document in documents.items()
        if PULL_REQUEST_EVENTS & triggers(name, document).keys()
    }
    if not found:
        message = "no workflow serves a pull request; the reader is broken"
        raise WorkflowError(message)
    while True:
        grown = found | _chained(found, documents)
        grown |= {callee for name in grown for callee in _callees(name, documents)}
        if grown == found:
            return {name: documents[name] for name in sorted(found)}
        found = grown


def pull_request_contacts(documents: dict[str, Document]) -> list[str]:
    """Report every way a pull request could reach CodeScene or its token.

    Every scalar is read, keys included, at every scope, so a workflow-level
    `defaults.run.shell`, an env value under an unrelated key or a callee's
    secret declaration is seen as readily as a step's script. The parser
    discards comments, so prose explaining the policy is not a violation.
    """
    found: list[str] = []
    for name, document in pull_request_closure(documents).items():
        texts = {_folded(text) for text in scalars(document)}
        found += [
            f"{name} {reason}"
            for marker, reason in PULL_REQUEST_FORBIDDEN
            if any(marker in text for text in texts)
        ]
        found += [
            f"{name} job {job_name} forwards every secret with `secrets: inherit`"
            for job_name, job in jobs(name, document).items()
            if job.get("secrets") == "inherit"
        ]
    return found


def retired_names(documents: dict[str, Document]) -> list[str]:
    """Report any retired checksum input, variable or refresher workflow."""
    found = [
        f"{name} still names {retired}"
        for name, document in documents.items()
        for retired in RETIRED
        if retired in name.casefold()
        or any(retired in _folded(text) for text in scalars(document))
    ]
    return sorted(set(found))


def _conjuncts(condition: object) -> frozenset[str]:
    """Split a step condition on `&&`, normalizing whitespace."""
    text = str(condition).strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2]
    return frozenset(" ".join(part.split()) for part in text.split("&&"))


def _expression(value: object) -> str:
    """Return an expression with its inner whitespace normalized."""
    return " ".join(str(value).replace("${{", "${{ ").replace("}}", " }}").split())


def upload_steps(documents: dict[str, Document]) -> list[tuple[str, Step]]:
    """Return every step in any workflow that calls the CodeScene uploader."""
    return [
        (name, step)
        for name, document in documents.items()
        for step in steps(name, document)
        if calls(step, UPLOAD_ACTION)
    ]


def _publisher_triggers(name: str, document: Document) -> list[str]:
    """Report a publisher answering anything but a push to main."""
    events = triggers(name, document)
    found = [
        f"{name} must not answer {event}"
        for event in events
        if event not in {"push", "workflow_dispatch"}
    ]
    if events.get("push") != {"branches": ["main"]}:
        found.append(f"{name} must answer exactly `push: branches: [main]`")
    return found


def _declares_group(concurrency: object) -> bool:
    """Return whether a workflow-level concurrency value names a group."""
    if isinstance(concurrency, dict):
        return "group" in concurrency
    return isinstance(concurrency, str)


def _publisher_concurrency(name: str, document: Document) -> list[str]:
    """Report a publisher whose runs could overlap or be cancelled."""
    concurrency = document.get("concurrency")
    if not _declares_group(concurrency):
        return [f"{name} needs a workflow-level concurrency group"]
    scopes = [concurrency]
    scopes += [job.get("concurrency") for job in jobs(name, document).values()]
    return [
        f"{name} cancels a publisher run in progress"
        for scope in scopes
        if isinstance(scope, dict)
        and scope.get("cancel-in-progress", False) is not False
    ]


def _upload_step(name: str, step: Step) -> list[str]:
    """Report an upload step not bound, guarded and moded as required."""
    env = step.get("env")
    inputs = step.get("with")
    env = env if isinstance(env, dict) else {}
    inputs = inputs if isinstance(inputs, dict) else {}
    found: list[str] = []
    if _conjuncts(step.get("if", "")) != UPLOAD_GUARD:
        found.append(f"{name} upload must be guarded on exactly {sorted(UPLOAD_GUARD)}")
    if _expression(env.get("CS_ACCESS_TOKEN")) != CREDENTIAL_BINDING:
        found.append(f"{name} upload step must bind {CREDENTIAL_BINDING}")
    if _expression(inputs.get("access-token")) != CREDENTIAL_INPUT:
        found.append(f"{name} upload must pass access-token {CREDENTIAL_INPUT}")
    if inputs.get("mode") != "upload":
        found.append(f"{name} upload must name `mode: upload`")
    return found


def _conditional_jobs(name: str, document: Document) -> list[str]:
    """Report a publisher job that could be skipped by its own condition."""
    return [
        f"{name} job {job_name} must run unconditionally"
        for job_name, job in jobs(name, document).items()
        if "if" in job
    ]


def _token_elsewhere(name: str, document: Document, upload: Step) -> list[str]:
    """Report the token anywhere in the publisher but its upload step."""
    rest = copy.deepcopy(document)
    for job in jobs(name, rest).values():
        job["steps"] = [
            s for s in typ.cast("list[Step]", job.get("steps", [])) if s != upload
        ]
    if any("cs_access_token" in _folded(text) for text in scalars(rest)):
        return [f"{name} puts CS_ACCESS_TOKEN in reach outside the upload step"]
    return []


def publisher_violations(documents: dict[str, Document]) -> list[str]:
    """Report anything but one guarded push-to-main publisher.

    The binding is asserted positively. A guard on `env.CS_ACCESS_TOKEN` is
    simply false when the binding is deleted or moved, so the upload would
    skip forever with nothing failing.
    """
    uploads = upload_steps(documents)
    if len(uploads) != 1:
        return [f"expected one CodeScene upload step, found {len(uploads)}"]
    name, upload = uploads[0]
    document = documents[name]
    return [
        *_publisher_triggers(name, document),
        *_publisher_concurrency(name, document),
        *_conditional_jobs(name, document),
        *_upload_step(name, upload),
        *_token_elsewhere(name, document, upload),
    ]


def coverage_steps(name: str, document: Document) -> list[Step]:
    """Return one workflow's generate-coverage steps."""
    return [step for step in steps(name, document) if calls(step, COVERAGE_ACTION)]


def _selection(step: Step) -> dict[str, object]:
    """Return a coverage step's inputs, less the artefact switch."""
    inputs = step.get("with")
    inputs = dict(inputs) if isinstance(inputs, dict) else {}
    inputs.pop("publish-artefact", None)
    return inputs


def _pull_request_lane(name: str, step: Step, trunk: Step) -> list[str]:
    """Report a pull-request coverage step that cannot ratchet like main."""
    inputs = step.get("with")
    inputs = inputs if isinstance(inputs, dict) else {}
    found: list[str] = []
    if step.get("if", PULL_REQUEST_GUARD) != PULL_REQUEST_GUARD:
        found.append(f"{name} coverage may run only as `{PULL_REQUEST_GUARD}`")
    if inputs.get("with-ratchet") != "true":
        found.append(f"{name} coverage must set with-ratchet 'true'")
    if inputs.get("publish-artefact") != "false":
        found.append(f"{name} coverage must set publish-artefact 'false'")
    if _selection(step) != _selection(trunk):
        found.append(f"{name} coverage selection differs from the publisher's")
    if step.get("uses") != trunk.get("uses"):
        found.append(f"{name} coverage pin differs from the publisher's")
    return found


def coverage_violations(documents: dict[str, Document]) -> list[str]:
    """Report coverage lanes that no longer ratchet against main's baseline.

    The publisher's generator writes the baseline and runs unconditionally;
    every pull-request generator reads it, so each must ratchet, publish no
    artefact and select exactly what the publisher selects, at the same pin.
    """
    uploads = upload_steps(documents)
    if len(uploads) != 1:
        return ["coverage lanes need exactly one publisher to compare against"]
    publisher = uploads[0][0]
    trunk_steps = coverage_steps(publisher, documents[publisher])
    if len(trunk_steps) != 1:
        return [f"{publisher} must generate coverage exactly once"]
    trunk = trunk_steps[0]
    found = [
        f"{publisher} {problem}"
        for problem, failed in (
            ("coverage must run unconditionally", "if" in trunk),
            (
                "coverage must set with-ratchet 'true'",
                _with(trunk, "with-ratchet") != "true",
            ),
            ("must pin shared actions by full SHA", not _pinned(trunk, uploads[0][1])),
            (
                "upload pin differs from its coverage pin",
                _ref(trunk) != _ref(uploads[0][1]),
            ),
        )
        if failed
    ]
    lanes = [
        (name, step)
        for name, document in pull_request_closure(documents).items()
        for step in coverage_steps(name, document)
    ]
    if not lanes:
        found.append("no pull-request lane generates coverage for the ratchet")
    for name, step in lanes:
        found += _pull_request_lane(name, step, trunk)
    return found


def _with(step: Step, key: str) -> object:
    """Return one input of a step, or None."""
    inputs = step.get("with")
    return inputs.get(key) if isinstance(inputs, dict) else None


def _ref(step: Step) -> str:
    """Return the ref a step's `uses:` names."""
    return str(step.get("uses", "")).partition("@")[2]


def _pinned(*called: Step) -> bool:
    """Return whether every step pins its action by a full commit SHA."""
    return all(PINNED.fullmatch(f"@{_ref(step)}") for step in called)
