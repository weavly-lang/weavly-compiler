from collections.abc import Collection
from functools import cache
from pathlib import Path

from lark import Token, Tree
from lark.lexer import PatternStr

from .parser import create_parser
from .type_checker import (
    BUILT_IN_FUNCTIONS,
    META_KEYS,
    Declarations,
    Location,
    check_types,
    source_location,
)
from .usage import find_warnings

Error = tuple[Location, str]
# (node id, meta key)
MetaRef = tuple[str, str]

# rule -> what its leading ID names, for duplicate errors.
_DECLARATION_KINDS = {
    "number_declaration": "variable",
    "string_declaration": "variable",
    "flag_declaration": "variable",
    "name_declaration": "variable",
    "extern_declaration": "variable",
    "pool_declaration": "pool",
    "slot_declaration": "slot",
    "meta_declaration": "meta key",
    "function_declaration": "function",
    "command_declaration": "command",
}
_NODE_KINDS = {"node_start": "node id"}
# rule -> what its target is called in errors.
_TARGET_KINDS = {
    "jump": "jump",
    "inline_jump": "jump",
    "detour": "detour",
    "node_option": "option",
}


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
        # meta value -> location of its key and the meta values it reads.
        self._meta_values: dict[MetaRef, tuple[Location, list[MetaRef]]] = {}
        # node ids with a label, and pool -> the node ids that join it.
        self._labelled: set[str] = set()
        self._pool_members: dict[str, list[str]] = {}
        # (node id or pool, location) of every node and pool option.
        self._offered_nodes: list[tuple[str, Location]] = []
        self._offered_pools: list[tuple[str, Location]] = []

    def add_file(self, file: Path, tree: Tree) -> None:
        self._record_unique(tree, file, _DECLARATION_KINDS, self._declared)
        self._record_unique(tree, file, _NODE_KINDS, self._node_ids)
        self._node_references.extend(
            (_TARGET_KINDS[rule], target, location)
            for rule, target, location in _id_locations(tree, _TARGET_KINDS, file)
        )
        self._record_call_targets(tree, file)
        self._check_number_ranges(tree, file)
        self._check_declared_names(tree, file)
        self._record_meta_values(tree, file)
        self._record_options(tree, file)
        self._trees.append((file, tree))

    def finish(self, declarations: list[dict]) -> list[Error]:
        """Check node references and types across all added files and return every error."""
        self.errors.extend(
            (location, f"{kind} target '{target}' matches no node")
            for kind, target, location in self._node_references
            if target not in self._node_ids
        )
        self.errors.extend(_meta_cycle_errors(self._meta_values))
        self._check_option_labels()
        collected = Declarations.collect(declarations)
        for file, tree in self._trees:
            self.errors.extend(check_types(tree, file, collected, self._node_ids))
        return self.errors

    def warnings(self) -> list[Error]:
        """Return warnings about declarations and meta keys that can't have an effect."""
        return find_warnings(self._trees)

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

    def _record_call_targets(self, tree: Tree, file: Path) -> None:
        for call in tree.find_data("node_call"):
            function, target = call.children
            self._node_references.append(
                (str(function), str(target), source_location(file, target))
            )

        for call in tree.find_data("meta_call"):
            target = call.children[0]
            self._node_references.append(("meta", str(target), source_location(file, target)))

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

    def _check_declared_names(self, tree: Tree, file: Path) -> None:
        reserved = (
            ("meta_declaration", META_KEYS, "a built-in meta key"),
            ("function_declaration", BUILT_IN_FUNCTIONS, "a built-in function"),
            ("command_declaration", _statement_keywords(), "a statement keyword"),
        )
        for rule, names, what in reserved:
            for declaration in tree.find_data(rule):
                name = declaration.children[0]
                if name in names:
                    self._error(file, name, f"'{name}' is {what}")

    def _record_meta_values(self, tree: Tree, file: Path) -> None:
        for node in tree.find_data("node"):
            node_id = str(node.children[0].children[0])
            for entry in node.find_data("meta_entry"):
                key = entry.children[0]
                reads = [
                    (str(call.children[0]), str(call.children[1]))
                    for call in entry.find_data("meta_call")
                ]
                self._meta_values.setdefault(
                    (node_id, str(key)), (source_location(file, key), reads)
                )

    def _record_options(self, tree: Tree, file: Path) -> None:
        for node in tree.find_data("node"):
            node_id = str(node.children[0].children[0])
            for entry in node.find_data("meta_entry"):
                key, *values = entry.children
                if key == "label":
                    self._labelled.add(node_id)
                elif key == "pool":
                    for value in values:
                        if isinstance(value, Tree) and value.data == "name":
                            pool = str(value.children[0])
                            self._pool_members.setdefault(pool, []).append(node_id)

        for option in tree.find_data("node_option"):
            target = option.children[0]
            self._offered_nodes.append((str(target), source_location(file, target)))
        for option in tree.find_data("pool_option"):
            for argument in option.children:
                if argument.data == "pool_name":
                    pool = argument.children[0]
                    self._offered_pools.append((str(pool), source_location(file, pool)))

    def _check_option_labels(self) -> None:
        self.errors.extend(
            (location, f"node '{target}' needs a label to be offered as an option")
            for target, location in self._offered_nodes
            if target in self._node_ids and target not in self._labelled
        )
        for pool, location in self._offered_pools:
            self.errors.extend(
                (
                    location,
                    f"node '{member}' in pool '{pool}' needs a label to be offered as an option",
                )
                for member in self._pool_members.get(pool, [])
                if member not in self._labelled
            )

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


@cache
def _statement_keywords() -> frozenset[str]:
    """Return the names after `@` that start a statement or block, not a command."""
    return frozenset(
        terminal.pattern.value[1:]
        for terminal in create_parser().terminals
        if isinstance(terminal.pattern, PatternStr) and terminal.pattern.value.startswith("@")
    )


def _meta_cycle_errors(values: dict[MetaRef, tuple[Location, list[MetaRef]]]) -> list[Error]:
    """Report every meta value that reads itself, directly or through other meta values."""
    errors: list[Error] = []
    finished: set[MetaRef] = set()
    path: list[MetaRef] = []

    def visit(ref: MetaRef) -> None:
        if ref in finished or ref not in values:
            return
        if ref in path:
            cycle = [*path[path.index(ref) :], ref]
            chain = " -> ".join(f"{node}.{key}" for node, key in cycle)
            errors.append((values[ref][0], f"meta key '{ref[1]}' reads itself: {chain}"))
            return
        path.append(ref)
        for read in values[ref][1]:
            visit(read)
        path.pop()
        finished.add(ref)

    for ref in values:
        visit(ref)
    return errors


def _number(child: Tree | Token | None) -> float | None:
    if child is None:
        return None
    if isinstance(child, Tree):
        return -float(child.children[0])
    return float(child)
