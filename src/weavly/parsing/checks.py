from collections.abc import Collection
from difflib import get_close_matches
from pathlib import Path

from lark import Token, Tree

from .type_checker import (
    NODE_FUNCTIONS,
    NUMBER_FUNCTIONS,
    Location,
    check_types,
    source_location,
)

Error = tuple[Location, str]

# rule -> what its leading ID names, for duplicate errors.
_DECLARATION_KINDS = {
    "number_declaration": "variable",
    "string_declaration": "variable",
    "flag_declaration": "variable",
    "extern_declaration": "variable",
    "pool_declaration": "pool",
    "slot_declaration": "slot",
}
_NODE_KINDS = {"node_start": "node id"}
_GOTO_RULES = frozenset({"goto", "inline_goto"})


class ProjectChecks:
    """Checks that need every file of the project, fed one parsed file at a time."""

    def __init__(self) -> None:
        self.errors: list[Error] = []
        self._trees: list[tuple[Path, Tree]] = []
        # name -> location of the first declaration or node with that name.
        self._declared: dict[str, Location] = {}
        self._node_ids: dict[str, Location] = {}
        # (kind, node id, location) of every reference to a node.
        self._node_references: list[tuple[str, str, Location]] = []

    def add_file(self, file: Path, tree: Tree) -> None:
        self._record_unique(tree, file, _DECLARATION_KINDS, self._declared)
        self._record_unique(tree, file, _NODE_KINDS, self._node_ids)
        self._node_references.extend(
            ("goto", target, location)
            for _, target, location in _id_locations(tree, _GOTO_RULES, file)
        )
        self._check_calls(tree, file)
        self._check_number_ranges(tree, file)
        self._trees.append((file, tree))

    def finish(self, declarations: list[dict]) -> list[Error]:
        """Check node references and types across all added files and return every error."""
        self.errors.extend(
            (location, f"{kind} target '{target}' matches no node")
            for kind, target, location in self._node_references
            if target not in self._node_ids
        )
        variables: dict[str, str] = {}
        for declaration in declarations:
            variables.setdefault(declaration["name"], declaration["type"])
        for file, tree in self._trees:
            self.errors.extend(check_types(tree, file, variables))
        return self.errors

    def _record_unique(
        self, tree: Tree, file: Path, kinds: dict[str, str], seen: dict[str, Location]
    ) -> None:
        """Record the names `kinds` rules define in `seen`, reporting any seen before."""
        for rule, name, location in _id_locations(tree, kinds, file):
            if name not in seen:
                seen[name] = location
                continue
            first_file, first_line, _ = seen[name]
            self.errors.append(
                (
                    location,
                    f"duplicate {kinds[rule]} '{name}', first declared at "
                    f"{first_file.as_posix()}:{first_line}",
                )
            )

    def _check_calls(self, tree: Tree, file: Path) -> None:
        for call in tree.find_data("node_call"):
            function, target = call.children
            if function in NODE_FUNCTIONS:
                self._node_references.append(
                    (str(function), str(target), source_location(file, target))
                )
            elif function in NUMBER_FUNCTIONS:
                self._error(file, target, f"{function}() takes numbers, not node id '{target}'")
            else:
                self._error(file, function, _unknown_function(function))

        for call in tree.find_data("call"):
            function, arguments = call.children
            if function in NODE_FUNCTIONS:
                message = f"{function}() takes a node id, or none for the current node"
            elif function in NUMBER_FUNCTIONS:
                count = 0 if arguments is None else len(arguments.children)
                message = _argument_count_error(function, count)
            else:
                message = _unknown_function(function)
            if message:
                self._error(file, function, message)

    def _check_number_ranges(self, tree: Tree, file: Path) -> None:
        for declaration in tree.find_data("number_declaration"):
            name, *numbers = declaration.children
            minimum, maximum, value = (_number(child) for child in numbers)

            if minimum is not None and maximum is not None and minimum > maximum:
                self._error(
                    file, name, f"number '{name}' has min {minimum:g} greater than max {maximum:g}"
                )
                continue

            default = "implicit default 0" if value is None else f"default {value:g}"
            value = value or 0.0
            if minimum is not None and value < minimum:
                self._error(file, name, f"number '{name}' has {default} below its min {minimum:g}")
            elif maximum is not None and value > maximum:
                self._error(file, name, f"number '{name}' has {default} above its max {maximum:g}")

    def _error(self, file: Path, item: Tree | Token, message: str) -> None:
        self.errors.append((source_location(file, item), message))


def _id_locations(
    tree: Tree, rules: Collection[str], file: Path
) -> list[tuple[str, str, Location]]:
    """Return (rule, id, location) for the leading ID of every matching rule, in source order."""
    locations = []
    for subtree in tree.iter_subtrees_topdown():
        if subtree.data in rules:
            id_token = subtree.children[0]
            locations.append((subtree.data, str(id_token), source_location(file, id_token)))
    return locations


def _argument_count_error(function: str, count: int) -> str | None:
    minimum, maximum = NUMBER_FUNCTIONS[function]
    if count >= minimum and (maximum is None or count <= maximum):
        return None
    expected = f"at least {minimum}" if maximum is None else str(minimum)
    noun = "argument" if expected == "1" else "arguments"
    return f"{function}() takes {expected} {noun}, got {count}"


def _unknown_function(function: str) -> str:
    message = f"unknown function '{function}'"
    matches = get_close_matches(function, [*NODE_FUNCTIONS, *NUMBER_FUNCTIONS], n=1)
    if matches:
        message += f", did you mean '{matches[0]}'?"
    return message


def _number(child: Tree | Token | None) -> float | None:
    if child is None:
        return None
    if isinstance(child, Tree):
        return -float(child.children[0])
    return float(child)
