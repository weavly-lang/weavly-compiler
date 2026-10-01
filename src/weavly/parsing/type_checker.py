from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
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
BUILT_IN_FUNCTIONS = frozenset({*NODE_FUNCTIONS, *NUMBER_FUNCTIONS, META_FUNCTION})

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
# declaration kind -> how errors name it, where that differs.
_KIND_NAMES = {"meta": "meta key"}


def source_location(file: Path, item: Tree | Token) -> Location:
    if isinstance(item, Token):
        return (file, item.line, item.column)
    return (file, item.meta.line, item.meta.column)


@dataclass
class Declarations:
    """The project's declarations by name, first declaration wins."""

    # name -> type
    variables: dict[str, str] = field(default_factory=dict)
    # every other declared name -> its kind
    kinds: dict[str, str] = field(default_factory=dict)
    # custom key -> type
    meta_keys: dict[str, str] = field(default_factory=dict)
    functions: dict[str, dict] = field(default_factory=dict)
    commands: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def collect(cls, declarations: list[dict]) -> "Declarations":
        collected = cls()
        for declaration in declarations:
            name, kind = declaration["name"], declaration.get("kind")
            if kind is None:
                collected.variables.setdefault(name, declaration["type"])
                continue
            collected.kinds.setdefault(name, _KIND_NAMES.get(kind, kind))
            if kind == "meta":
                collected.meta_keys.setdefault(name, declaration["type"])
            elif kind == "function":
                collected.functions.setdefault(name, declaration)
            elif kind == "command":
                collected.commands.setdefault(name, declaration)
        return collected


def check_types(
    tree: Tree, file: Path, declarations: Declarations, nodes: Collection[str]
) -> list[tuple[Location, str]]:
    """Check `tree` against the project's declarations and node ids."""
    return _TypeChecker(file, declarations, nodes).check(tree)


class _TypeChecker:
    def __init__(self, file: Path, declarations: Declarations, nodes: Collection[str]) -> None:
        self.file = file
        self.variables = declarations.variables
        self.kinds = declarations.kinds
        self.meta_keys = META_KEYS | declarations.meta_keys
        self.functions = declarations.functions
        self.commands = declarations.commands
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
        name, arguments = tree.children
        declaration = self.commands.get(str(name))
        if declaration is not None:
            self._expect_arguments(name, f"@{name}", declaration["params"], _items(arguments))
            return
        for argument in _items(arguments):
            self._infer(argument)
        if name in self.functions:
            self._error(name, f"'{name}' is a function and can't be a statement")
        else:
            self._error(name, _unknown("command", str(name), self.commands))

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
            self._error(key, _unknown("meta key", str(key), self.meta_keys))
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
        name = str(function)
        if name in NUMBER_FUNCTIONS:
            message = _count_error(f"{name}()", len(_items(arguments)), *NUMBER_FUNCTIONS[name])
            if message:
                self._error(function, message)
            for argument in _items(arguments):
                self._expect(argument, NUMBER, f"{name}()")
            return NUMBER

        declaration = self.functions.get(name)
        if declaration is not None:
            self._expect_arguments(function, f"{name}()", declaration["params"], _items(arguments))
            return declaration["returns"]

        for argument in _items(arguments):
            self._infer(argument)
        if name in NODE_FUNCTIONS:
            message = f"{name}() takes a node id, or none for the current node"
        elif name == META_FUNCTION:
            message = "meta() takes a meta key, or a node id and a meta key"
        elif name in self.commands:
            message = f"'{name}' is a command and has no value"
        else:
            message = _unknown("function", name, [*BUILT_IN_FUNCTIONS, *self.functions])
        self._error(function, message)
        return None

    def _expect_arguments(
        self, where: Token, label: str, params: list[dict], arguments: list
    ) -> None:
        message = _count_error(label, len(arguments), len(params), len(params))
        if message:
            self._error(where, message)
        for param, argument in zip(params, arguments):
            if param["type"] in NAME_TYPES and _is_name(argument):
                self._expect_name(argument, param["type"])
            else:
                self._expect(argument, param["type"], f"{label} argument '{param['name']}'")
        for argument in arguments[len(params) :]:
            self._infer(argument)

    def _infer_meta_call(self, tree: Tree) -> str | None:
        key = tree.children[1]
        if key in _UNREADABLE_META_KEYS:
            self._error(key, f"meta() can't read {key}")
            return None
        value_type = self.meta_keys.get(str(key))
        if value_type is None:
            self._error(key, _unknown("meta key", str(key), self.meta_keys))
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
        elif name in self.kinds:
            self._error(tree, f"'{name}' is a {self.kinds[name]}, not a node, pool or slot")
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


def _items(arguments: Tree | None) -> list:
    return [] if arguments is None else arguments.children


def _count_error(label: str, count: int, minimum: int, maximum: int | None) -> str | None:
    if count >= minimum and (maximum is None or count <= maximum):
        return None
    expected = f"at least {minimum}" if maximum is None else str(minimum)
    noun = "argument" if expected == "1" else "arguments"
    return f"{label} takes {expected} {noun}, got {count}"


def _unknown(kind: str, name: str, known: Iterable[str]) -> str:
    message = f"unknown {kind} '{name}'"
    matches = get_close_matches(name, list(known), n=1)
    if matches:
        message += f", did you mean '{matches[0]}'?"
    return message
