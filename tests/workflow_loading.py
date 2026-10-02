"""Load a GitHub Actions workflow strictly enough for the coverage contract.

PyYAML keeps the last of two equal mapping keys and says nothing, so a
workflow declaring ``steps`` or ``with`` twice would parse into a document
that hides a coverage step or one of its inputs. This loader refuses such a
document, and one that is not a mapping, with an error naming the problem.
"""

from __future__ import annotations

import typing as typ

import yaml
from yaml.constructor import ConstructorError

#: A parsed workflow. The key type is ``object`` because YAML 1.1 resolves an
#: unquoted ``on:`` to the boolean ``True``.
type Document = dict[object, object]


class WorkflowReadingError(Exception):
    """Raised when a workflow cannot be read into a shape the rules trust."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """A `yaml.SafeLoader` refusing a mapping that declares a key twice.

    PyYAML keeps the last of two equal keys and says nothing, so a job
    declaring `runs-on` twice parses into a document holding only the
    second value while the rules read the half GitHub may not run.
    """

    @typ.override
    def construct_mapping(
        self, node: yaml.MappingNode, deep: bool = False
    ) -> dict[typ.Hashable, typ.Any]:
        """Construct one mapping, refusing a key already seen in it.

        Raises
        ------
        ConstructorError
            If a key appears twice, naming it and where it appears.

        """
        seen: set[object] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                context = "while constructing a mapping"
                problem = f"found duplicate key {key!r}"
                raise ConstructorError(
                    context, node.start_mark, problem, key_node.start_mark
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def load_workflow(text: str) -> Document:
    r"""Parse one workflow, refusing duplicate keys and non-mapping documents.

    Raises
    ------
    WorkflowReadingError
        If the text is not YAML, repeats a key, or is not a mapping.

    Examples
    --------
    >>> load_workflow("on: push\njobs: {}\n")
    {True: 'push', 'jobs': {}}

    """
    # What `yaml.load` does, spelt out so no linter mistakes the strict
    # SafeLoader subclass for an unsafe loader.
    loader = _UniqueKeyLoader(text)
    try:
        parsed = loader.get_single_data()
    except yaml.YAMLError as error:
        message = f"not a workflow document: {error}"
        raise WorkflowReadingError(message) from error
    finally:
        loader.dispose()
    if not isinstance(parsed, dict):
        message = "a workflow must parse to a top-level mapping"
        raise WorkflowReadingError(message)
    return typ.cast("Document", parsed)
