from collections.abc import Collection
from difflib import get_close_matches
from pathlib import Path

from lark import Token, Tree

Location = tuple[Path, int, int]

NUMBER = "number"
STRING = "string"
FLAG = "flag"
NODE = "node"
POOL = "pool"
SLOT = "slot"
NAME_TYPES = (NODE, POOL, SLOT)

# name -> result type.
NODE_FUNCTIONS = {"visited": FLAG, "visit_count": NUMBER, "skip_count": NUMBER}
# name -> (min, max) argument count, max None for no limit.
NUMBER_FUNCTIONS = {
    "random": (2, 2),
    "min": (2, None),
    "max": (2, None),
    "clamp": (3, 3),
    "round": (1, 1),
    "floor": (1, 1),
    "ceil": (1, 1),
    "abs": (1, 1),
}

META_FUNCTION = "meta"

# built-in key -> type of its value.
META_KEYS = {
    "pool": POOL,
    "slot": SLOT,
    "when": FLAG,
    "priority": NUMBER,
    "weight": NUMBER,
    "once": FLAG,
}
# Built-in keys meta() can't read: lists, or not written to the output.
_UNREADABLE_META_KEYS = frozenset({"pool", "slot", "once"})

_LITERAL_TYPES = {"NUMBER": NUMBER, "STRING": STRING, "TRUE": FLAG, "FALSE": FLAG}
_ARITHMETIC = {"add": "+", "sub": "-", "mul": "*", "div": "/"}
_LOGIC = {"and_": "and", "or_": "or"}
_EQUALITY = frozenset({"==", "!="})


def source_location(file: Path, item: Tree | Token) -> Location:
    if isinstance(item, Token):
        return (file, item.line, item.column)
    return (file, item.meta.line, item.meta.column)


def check_types(
    tree: Tree,
    file: Path,
    variables: dict[str, str],
    kinds: dict[str, str],
    meta_keys: dict[str, str],
    nodes: Collection[str],
) -> list[tuple[Location, str]]:
    """Check `tree` against variables (name -> type), other declarations (name -> kind),
    custom meta keys (name -> type) and nodes."""
    return _TypeChecker(file, variables, kinds, meta_keys, nodes).check(tree)


class _TypeChecker:
    def __init__(
        self,
        file: Path,
        variables: dict[str, str],
        kinds: dict[str, str],
        meta_keys: dict[str, str],
        nodes: Collection[str],
    ) -> None:
        self.file = file
        self.variables = variables
        self.kinds = kinds
        self.meta_keys = META_KEYS | meta_keys
        self.nodes = nodes
        self.errors: list[tuple[Location, str]] = []

    def check(self, tree: Tree) -> list[tuple[Location, str]]:
        for subtree in tree.iter_subtrees_topdown():
            handler = getattr(self, f"_check_{subtree.data}", None)
            if handler is not None:
                handler(subtree)
        return self.errors

    # =====================
    # Statements
    # =====================

    def _check_name_declaration(self, tree: Tree) -> None:
        _, name_type, value = tree.children
        self._expect_name(value, str(name_type.children[0]))

    def _check_name_default(self, tree: Tree) -> None:
        name_type, value = tree.children
        self._expect_name(value, str(name_type.children[0]))

    def _check_set(self, tree: Tree) -> None:
        variable, expression = tree.children
        declared = self._variable(variable)
        actual = self._infer(expression, declared)
        if declared and actual and declared != actual:
            self._error(
                expression, f"@set ${variable.children[0]} needs a {declared}, got a {actual}"
            )

    def _check_increase(self, tree: Tree) -> None:
        self._expect_variable(tree.children[0], NUMBER, "@increase")

    def _check_decrease(self, tree: Tree) -> None:
        self._expect_variable(tree.children[0], NUMBER, "@decrease")

    def _check_setflag(self, tree: Tree) -> None:
        self._expect_variable(tree.children[0], FLAG, "@setflag")

    def _check_clearflag(self, tree: Tree) -> None:
        self._expect_variable(tree.children[0], FLAG, "@clearflag")

    def _check_draw(self, tree: Tree) -> None:
        for pool in tree.children:
            self._expect_name(pool, POOL)

    def _check_command(self, tree: Tree) -> None:
        arguments = tree.children[1]
        for argument in arguments.children if arguments is not None else []:
            self._infer(argument)

    def _check_condition(self, tree: Tree) -> None:
        self._expect(tree.children[0], FLAG, "condition")

    def _check_case(self, tree: Tree) -> None:
        weight = tree.children[1]
        if weight is not None:
            self._expect(weight, NUMBER, "random weight")

    def _check_meta_block(self, tree: Tree) -> None:
        seen = set()
        for entry in tree.children:
            key = entry.children[0]
            if str(key) in seen:
                self._error(key, f"duplicate meta key '{key}'")
            seen.add(str(key))

    def _check_meta_entry(self, tree: Tree) -> None:
        key, *values = tree.children
        expected = self.meta_keys.get(str(key))
        if expected is None:
            self._error(key, self._unknown_meta_key(str(key)))
            return

        if key in ("pool", "slot"):
            for value in values:
                if _is_name(value):
                    self._expect_name(value, expected)
                else:
                    self._error(value, f"{key} takes {expected} names, not expressions")
            return

        if len(values) > 1:
            self._error(values[1], f"{key} takes a single value, got {len(values)}")
            return
        value = values[0]
        if key == "once":
            if not isinstance(value, Token) or value.type not in ("TRUE", "FALSE"):
                self._error(value, "once needs true or false")
        else:
            self._expect(value, expected, str(key))

    def _check_character_line(self, tree: Tree) -> None:
        self._expect_variable(tree.children[0], STRING, "character name")

    def _check_interpolation(self, tree: Tree) -> None:
        self._infer(tree.children[0])

    # =====================
    # Expressions
    # =====================

    def _infer(self, node: Tree | Token, expected: str | None = None) -> str | None:
        """Return the type of an expression, or None if it has no known type.

        `expected` picks the type of a name that is both a node and a pool or slot.
        """
        if isinstance(node, Token):
            return _LITERAL_TYPES[node.type]

        rule = node.data
        if rule == "variable":
            return self._variable(node)
        if rule == "name":
            return self._infer_name(node, expected)
        if rule in _ARITHMETIC:
            for operand in node.children:
                self._expect(operand, NUMBER, f"'{_ARITHMETIC[rule]}'")
            return NUMBER
        if rule == "neg":
            self._expect(node.children[0], NUMBER, "'-'")
            return NUMBER
        if rule in _LOGIC:
            for operand in node.children:
                self._expect(operand, FLAG, f"'{_LOGIC[rule]}'")
            return FLAG
        if rule == "not_":
            self._expect(node.children[0], FLAG, "'not'")
            return FLAG
        if rule == "compare":
            left, operator, right = node.children
            left_type = None if _is_name(left) else self._infer(left)
            right_type = self._infer(right, left_type)
            if _is_name(left):
                left_type = self._infer(left, right_type)
            if left_type and right_type and left_type != right_type:
                self._error(
                    node,
                    f"'{operator}' needs both sides of the same type, "
                    f"got a {left_type} and a {right_type}",
                )
            elif left_type in NAME_TYPES and operator not in _EQUALITY:
                self._error(node, f"'{operator}' can't compare {left_type}s")
            return FLAG
        if rule == "node_call":
            return NODE_FUNCTIONS.get(str(node.children[0]))
        if rule == "meta_call":
            return self._infer_meta_call(node)
        if rule == "call":
            return self._infer_call(node)
        raise ValueError(f"Unhandled expression: {rule}")

    def _infer_call(self, node: Tree) -> str | None:
        function, arguments = node.children
        is_number_function = function in NUMBER_FUNCTIONS
        for argument in arguments.children if arguments is not None else []:
            if is_number_function:
                self._expect(argument, NUMBER, f"{function}()")
            else:
                self._infer(argument)
        return NUMBER if is_number_function else None

    def _infer_meta_call(self, tree: Tree) -> str | None:
        key = tree.children[1]
        if key in _UNREADABLE_META_KEYS:
            self._error(key, f"meta() can't read {key}")
            return None
        value_type = self.meta_keys.get(str(key))
        if value_type is None:
            self._error(key, self._unknown_meta_key(str(key)))
        return value_type

    # =====================
    # Helpers
    # =====================

    def _variable(self, tree: Tree) -> str | None:
        name = str(tree.children[0])
        declared = self.variables.get(name)
        if declared is None and name in self.kinds:
            self._error(tree, f"'{name}' is a {self.kinds[name]}, not a variable")
        elif declared is None:
            self._error(tree, f"variable '{name}' isn't declared")
        return declared

    def _infer_name(self, tree: Tree, expected: str | None) -> str | None:
        name = str(tree.children[0])
        types = self._name_types(name)
        if expected in types:
            return expected
        if types:
            return types[0]
        if name in self.variables:
            self._error(tree, f"'{name}' is a variable, write ${name}")
        elif name in self.meta_keys and name not in _UNREADABLE_META_KEYS:
            self._error(tree, f"'{name}' is a meta key, write meta({name})")
        else:
            self._error(tree, f"'{name}' isn't a node, pool or slot")
        return None

    def _expect_name(self, item: Tree | Token, expected: str) -> None:
        name = str(item if isinstance(item, Token) else item.children[0])
        types = self._name_types(name)
        if expected in types:
            return
        actual = types[0] if types else self.kinds.get(name)
        if name in self.variables:
            self._error(item, f"'{name}' is a variable, not a {expected}")
        elif actual:
            self._error(item, f"'{name}' is a {actual}, not a {expected}")
        elif expected == NODE:
            self._error(item, f"'{name}' matches no node")
        else:
            self._error(item, f"{expected} '{name}' isn't declared")

    def _unknown_meta_key(self, key: str) -> str:
        message = f"unknown meta key '{key}'"
        matches = get_close_matches(key, self.meta_keys, n=1)
        if matches:
            message += f", did you mean '{matches[0]}'?"
        return message

    def _name_types(self, name: str) -> list[str]:
        kind = self.kinds.get(name)
        types = [kind] if kind in (POOL, SLOT) else []
        if name in self.nodes:
            types.append(NODE)
        return types

    def _expect(self, node: Tree | Token, expected: str, context: str) -> None:
        actual = self._infer(node, expected)
        if actual and actual != expected:
            self._error(node, f"{context} needs a {expected}, got a {actual}")

    def _expect_variable(self, tree: Tree, expected: str, context: str) -> None:
        declared = self._variable(tree)
        if declared and declared != expected:
            self._error(
                tree,
                f"{context} needs a {expected} variable, "
                f"'{tree.children[0]}' is a {declared}",
            )

    def _error(self, node: Tree | Token, message: str) -> None:
        self.errors.append((source_location(self.file, node), message))


def _is_name(value: Tree | Token) -> bool:
    return isinstance(value, Tree) and value.data == "name"
