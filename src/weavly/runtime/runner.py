from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import readchar
import typer

if TYPE_CHECKING:
    from .model import Node, Option, Statement

_VARIABLE_PATTERN = re.compile(r"\{\$([^}]+)\}")


class Context:
    def __init__(self, show_debug_info: bool = False) -> None:
        self.wait_for_input: bool = False
        self.stack: ExecutionStack = ExecutionStack(self)
        self.variables: VariableStore = VariableStore()
        self.nodes: NodeStore = NodeStore(self.stack)
        self.output: OutputHandler = OutputHandler(self.variables, show_debug_info)
        self.options: OptionHandler = OptionHandler(self.stack, self.output)

    def run_dialog(self, node_id: str) -> None:
        self.wait_for_input = True
        self.nodes.enter(node_id)

        while True:
            if self.options.has_pending_options:
                try:
                    line = typer.prompt("Choose Option")
                    self.options.choose_option(int(line))
                except KeyboardInterrupt:
                    typer.echo("\nStopped.")
                    raise typer.Exit()
                continue

            self.stack.run_step()

            if self.wait_for_input:
                try:
                    while True:
                        ch = readchar.readkey()  # blocks, no echo
                        if ch == " ":
                            break
                    self.wait_for_input = False
                except KeyboardInterrupt:
                    typer.echo("\nStopped.")
                    raise typer.Exit()

            if self.stack.finished:
                break


@dataclass
class NodeStore:
    stack: ExecutionStack
    nodes: dict[str, dict] = field(default_factory=dict)

    def add(self, node: Node) -> None:
        self.nodes[node.id] = node

    def enter(self, node_id: str) -> None:
        if node_id not in self.nodes:
            raise ValueError(f"There is no node with id: {node_id}")

        self.body_frame_stack = []
        node: Node = self.nodes.get(node_id)
        self.stack.push(node.body)


@dataclass
class VariableStore:
    values: dict[str, Any] = field(default_factory=dict)

    def set(self, name: str, value: Any) -> None:
        self.values[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        """Get variable value with optional default.

        Args:
            name: Variable name to retrieve
            default: Default value if variable doesn't exist (None raises KeyError)

        Returns:
            Variable value or default

        Raises:
            KeyError: If variable doesn't exist and no default provided
        """
        if default is None and name not in self.values:
            raise KeyError(
                f"Unknown variable: '{name}'. Available variables: {list(self.values.keys())}"
            ) from None
        return self.values.get(name, default)

    def inject(self, text: str) -> str:
        return _VARIABLE_PATTERN.sub(lambda m: str(self.get(m.group(1).strip())), text)


class ExecutionStack:
    def __init__(self, context: Context) -> None:
        self.context: Context = context
        self._stack: list[BodyFrame] = []
        self.finished: bool = False

    def push(self, body: list[Statement]) -> None:
        body_frame: BodyFrame = BodyFrame(body, 0)
        self._stack.append(body_frame)

    def run_step(self) -> None:
        if not self._stack:
            self.finished = True
            return

        frame: BodyFrame = self._stack[-1]
        if not frame.has_next:
            self._stack.pop()
            return

        statement: Statement = frame.get_current_statement()
        statement.execute(self.context)
        frame.counter += 1


@dataclass
class BodyFrame:
    statements: list[Statement]
    counter: int

    def get_current_statement(self) -> Statement:
        if self.counter < len(self.statements):
            return self.statements[self.counter]
        raise IndexError(
            f"Trying to access index {self.counter} of body frame with length {len(self.statements)}"
        )

    @property
    def has_next(self) -> bool:
        return self.counter < len(self.statements)


@dataclass
class OutputHandler:
    variables: VariableStore
    show_debug_info: bool

    def print_line(self, raw_text: str) -> None:
        rendered_text = self.variables.inject(raw_text)
        print(rendered_text)

    def print_info(self, text: str) -> None:
        if self.show_debug_info:
            print(text)


class OptionHandler:
    def __init__(self, stack: ExecutionStack, output: OutputHandler) -> None:
        self.pending_options: list[Option] = []
        self.stack: ExecutionStack = stack
        self.output: OutputHandler = output

    def set_pending_options(self, options: list[Option]) -> None:
        self.pending_options = options

    @property
    def has_pending_options(self) -> bool:
        return bool(self.pending_options)

    def choose_option(self, index: int) -> None:
        if index < 0 or index >= len(self.pending_options):
            raise ValueError(f"There is no pending option with index {index}")
        option = self.pending_options[index]
        self.pending_options = []
        self.stack.push(option.body)
        self.output.print_line("")
