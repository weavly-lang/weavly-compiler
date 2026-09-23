import re
from pathlib import Path

from lark import Token, Tree

Location = tuple[Path, int, int]

NUMBER = "number"
STRING = "string"
FLAG = "flag"

# name -> result type.
NODE_FUNCTIONS = {"visited": FLAG, "visit_count": NUMBER}
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

_LITERAL_TYPES = {"NUMBER": NUMBER, "STRING": STRING, "TRUE": FLAG, "FALSE": FLAG}
_ARITHMETIC = {"add": "+", "sub": "-", "mul": "*", "div": "/"}
_LOGIC = {"and_": "and", "or_": "or"}
_TEXT_TOKENS = frozenset({"TEXT", "STRING"})
_INTERPOLATION = re.compile(r"\{\$([A-Za-z_][A-Za-z0-9_]*)\}")


def source_location(file: Path, item: Tree | Token) -> Location:
    if isinstance(item, Token):
        return (file, item.line, item.column)
    return (file, item.meta.line, item.meta.column)


def check_types(
    tree: Tree, file: Path, variables: dict[str, str]
) -> list[tuple[Location, str]]:
    """Check every variable use in `tree` against `variables` (name -> type)."""
    return _TypeChecker(file, variables).check(tree)


class _TypeChecker:
    def __init__(self, file: Path, variables: dict[str, str]) -> None:
        self.file = file
        self.variables = variables
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

    def _check_set(self, tree: Tree) -> None:
        variable, expression = tree.children
        declared = self._variable(variable)
        actual = self._infer(expression)
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

    def _check_condition(self, tree: Tree) -> None:
        self._expect(tree.children[0], FLAG, "condition")

    def _check_case(self, tree: Tree) -> None:
        weight = tree.children[1]
        if weight is not None:
            self._expect(weight, NUMBER, "random weight")

    def _check_character_line(self, tree: Tree) -> None:
        self._expect_variable(tree.children[0], STRING, "character name")
        self._check_text(tree)

    def _check_narration_line(self, tree: Tree) -> None:
        self._check_text(tree)

    def _check_named_character_line(self, tree: Tree) -> None:
        self._check_text(tree)

    def _check_option(self, tree: Tree) -> None:
        self._check_text(tree)

    def _check_hint_option(self, tree: Tree) -> None:
        self._check_text(tree)

    def _check_continue_(self, tree: Tree) -> None:
        self._check_text(tree)

    def _check_text(self, tree: Tree) -> None:
        for token in tree.children:
            if not isinstance(token, Token) or token.type not in _TEXT_TOKENS:
                continue
            for match in _INTERPOLATION.finditer(token.value):
                name = match.group(1)
                if name not in self.variables:
                    column = token.column + match.start(1) - 1
                    self.errors.append(
                        ((self.file, token.line, column), f"variable '{name}' isn't declared")
                    )

    # =====================
    # Expressions
    # =====================

    def _infer(self, node: Tree | Token) -> str | None:
        """Return the type of an expression, or None if it has no known type."""
        if isinstance(node, Token):
            return _LITERAL_TYPES[node.type]

        rule = node.data
        if rule == "variable":
            return self._variable(node)
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
            left_type, right_type = self._infer(left), self._infer(right)
            if left_type and right_type and left_type != right_type:
                self._error(
                    node,
                    f"'{operator}' needs both sides of the same type, "
                    f"got a {left_type} and a {right_type}",
                )
            return FLAG
        if rule == "node_call":
            return NODE_FUNCTIONS.get(str(node.children[0]))
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

    # =====================
    # Helpers
    # =====================

    def _variable(self, tree: Tree) -> str | None:
        name = str(tree.children[0])
        declared = self.variables.get(name)
        if declared is None:
            self._error(tree, f"variable '{name}' isn't declared")
        return declared

    def _expect(self, node: Tree | Token, expected: str, context: str) -> None:
        actual = self._infer(node)
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
