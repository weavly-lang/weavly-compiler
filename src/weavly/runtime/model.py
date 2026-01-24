from __future__ import annotations

import operator
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .runner import Context

UNARY_OPERATORS = {"not": operator.not_}

BINARY_OPERATORS = {
    "or": operator.or_,
    "and": operator.and_,
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
}

# =====================
# Nodes
# =====================


@dataclass
class Node:
    id: str
    body: list[Statement]


# =====================
# Statements
# =====================


@dataclass
class Statement(ABC):
    @abstractmethod
    def execute(self, context: Context) -> None:
        pass


@dataclass
class LineStatement(Statement):
    text: str


@dataclass
class NarrationLine(LineStatement):
    def execute(self, context: Context) -> None:
        context.output.print_line(self.text)
        context.wait_for_input = True


@dataclass
class CharacterLine(LineStatement):
    id: str

    def execute(self, context: Context) -> None:
        context.output.print_line(f"{self.id}: {self.text}")
        context.wait_for_input = True


@dataclass
class SetStatement(Statement):
    id: str
    expression: Expression

    def execute(self, context: Context) -> None:
        value = self.expression.evaluate(context)
        expression_string = self.expression.string(context)
        context.variables.set(self.id, value)

        text = (
            f"[SET] variable={self.id}, value={value}, expression={expression_string}"
        )
        context.output.print_info(text)


@dataclass
class GotoStatement(Statement):
    id: str

    def execute(self, context: Context) -> None:
        context.output.print_info(f"[GOTO] {self.id}")
        context.nodes.enter(self.id)


@dataclass
class FinishStatement(Statement):
    def execute(self, context: Context) -> None:
        context.output.print_info("[FINISH]")


@dataclass
class CommandStatement(Statement):
    id: str
    text: str

    def execute(self, context: Context) -> None:
        context.output.print_info(f"[COMMAND] id={self.id}, text='{self.text}'")


# =====================
# If Block
# =====================


@dataclass
class IfBlock(Statement):
    cases: list[IfCase]

    def execute(self, context: Context) -> None:
        case_choosen = False
        for case in self.cases:
            result = case.condition.evaluate(context)
            if not isinstance(result, bool):
                raise ValueError(f"Cant evaluate expression to bool: {case.condition}")

            chose_this_case = result and not case_choosen

            if chose_this_case:
                context.stack.push(case.body)
                case_choosen = True

            context.output.print_info(
                f"[If] condition={result}"
                f", executed={chose_this_case}"
                f", expression={case.condition.string(context)}"
            )


@dataclass
class IfCase:
    condition: Expression
    body: list[Statement]


# =====================
# Option Block
# =====================


@dataclass
class OptionBlock(Statement):
    options: list[Option]

    def execute(self, context: Context) -> None:
        context.options.set_pending_options(self.options)

        context.output.print_line("\n=== Options ===")
        for index, option in enumerate(self.options):
            result = option.condition.evaluate(context)
            if not isinstance(result, bool):
                raise ValueError(
                    f"Cant evaluate expression to bool: {option.condition}"
                )

            condition_string = option.condition.string(context)
            context.output.print_info(
                f"[OPTION] condition={result}, expression={condition_string}"
            )
            text = f"[{index}] {option.text}"
            context.output.print_line(text) if result else context.output.print_info(
                text
            )


@dataclass
class Option:
    condition: Expression
    text: str
    body: list[Statement]


# =====================
# Expressions
# =====================


class Expression(ABC):
    @abstractmethod
    def evaluate(self, context: Context) -> Any:
        pass

    def string(self, context: Context) -> str:
        pass


@dataclass
class UnaryExpression(Expression):
    op: str
    expression: Expression

    def evaluate(self, context: Context) -> bool:
        expression = self.expression.evaluate(context)
        try:
            return UNARY_OPERATORS[self.op](expression)
        except KeyError:
            raise ValueError(f"Unknown unary operator: {self.op}")

    def string(self, context: Context) -> str:
        expression = self.expression.string(context)
        return f"({self.op}({expression}))"


@dataclass
class BinaryExpression(Expression):
    op: str
    left: Expression
    right: Expression

    def evaluate(self, context: Context) -> bool:
        left = self.left.evaluate(context)
        right = self.right.evaluate(context)

        # Prevent division by zero
        if self.op == "/" and right == 0:
            raise ValueError(f"Division by zero: {left} / {right}")

        try:
            return BINARY_OPERATORS[self.op](left, right)
        except KeyError:
            raise ValueError(f"Unknown binary operator: {self.op}")

    def string(self, context: Context) -> str:
        left = self.left.string(context)
        right = self.right.string(context)
        return f"({left} {self.op} {right})"


@dataclass
class TrueExpression(Expression):
    def evaluate(self, context: Context) -> bool:
        return True

    def string(self, context: Context) -> str:
        return "true"


@dataclass
class FalseExpression(Expression):
    def evaluate(self, context: Context) -> bool:
        return False

    def string(self, context: Context) -> str:
        return "false"


@dataclass
class Number(Expression):
    value: float

    def evaluate(self, context: Context) -> float:
        return self.value

    def string(self, context: Context) -> str:
        return str(self.value)


@dataclass
class String(Expression):
    value: str

    def evaluate(self, context: Context) -> str:
        return self.value

    def string(self, context: Context) -> str:
        return self.value


@dataclass
class Variable(Expression):
    variable: str

    def evaluate(self, context: Context) -> Any:
        return context.variables.get(self.variable)

    def string(self, context: Context) -> str:
        value = context.variables.get(self.variable)
        return f"${self.variable}:{value}"
