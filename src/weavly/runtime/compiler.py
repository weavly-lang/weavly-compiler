from typing import Any, TypeVar

from .model import (
    BinaryExpression,
    CharacterLine,
    CommandStatement,
    Expression,
    FalseExpression,
    FinishStatement,
    GotoStatement,
    IfBlock,
    IfCase,
    NarrationLine,
    Node,
    Number,
    Option,
    OptionBlock,
    SetStatement,
    Statement,
    String,
    TrueExpression,
    UnaryExpression,
    Variable,
)

T = TypeVar("T")


# =====================
# Field Keys
# =====================

# Top-level keys
KEY_NODES = "nodes"

# Common keys
KEY_ID = "id"
KEY_BODY = "body"
KEY_TYPE = "type"
KEY_TEXT = "text"

# Expression keys
KEY_EXPRESSION = "expression"
KEY_CONDITION = "condition"
KEY_VARIABLE = "variable"
KEY_OP = "op"
KEY_LEFT = "left"
KEY_RIGHT = "right"

# Block keys
KEY_CASES = "cases"
KEY_OPTIONS = "options"

# Type values
TYPE_NARRATION = "narration"
TYPE_CHARACTER = "character"
TYPE_IF = "if"
TYPE_OPTION = "option"
TYPE_SET = "set"
TYPE_GOTO = "goto"
TYPE_FINISH = "finish"
TYPE_COMMAND = "command"


# =====================
# Helpers
# =====================


def get_required(
    data: dict[str, Any], key: str, field_type: type[T] | None = None
) -> T:
    """Get a required field from data dictionary.

    Args:
        data: Dictionary to get value from
        key: Key to retrieve
        field_type: Expected type (optional, for better error messages)

    Returns:
        The value

    Raises:
        ValueError: If key is missing or value is None
    """
    value = data.get(key)
    if value is None:
        raise ValueError(f"Missing required field: '{key}'")

    if field_type is not None and not isinstance(value, field_type):
        raise ValueError(
            f"Field '{key}' has wrong type: expected {field_type.__name__}, "
            f"got {type(value).__name__}"
        )

    return value


# =====================
# Nodes
# =====================


def compile_nodes(data: dict[str, Any]) -> list[Node]:
    """Compile JSON data into a list of Node objects.

    Args:
        data: Dictionary containing 'nodes' key with list of node definitions

    Returns:
        List of compiled Node objects
    """
    nodes: list[Node] = []
    nodes_data: list[dict[str, Any]] = get_required(data, KEY_NODES, list)
    for node_data in nodes_data:
        nodes.append(compile_node(node_data))
    return nodes


def compile_node(data: dict[str, Any]) -> Node:
    """Compile a single node from JSON data.

    Args:
        data: Dictionary containing node data with 'id' and 'body' fields

    Returns:
        Compiled Node object
    """
    id = get_required(data, KEY_ID, str)
    body = compile_statements(get_required(data, KEY_BODY, list))
    return Node(id, body)


# =====================
# Statements
# =====================


def compile_statements(data: list[dict[str, Any]]) -> list[Statement]:
    """Compile a list of statements from JSON data.

    Args:
        data: List of dictionaries, each representing a statement

    Returns:
        List of compiled Statement objects
    """
    statements = []
    for statement_data in data:
        statements.append(compile_statement(statement_data))
    return statements


def compile_statement(data: dict[str, Any]) -> Statement:
    """Compile a single statement from JSON data.

    Dispatches to the appropriate compile function based on statement type.

    Args:
        data: Dictionary containing statement data with 'type' field

    Returns:
        Compiled Statement object of the appropriate subclass

    Raises:
        ValueError: If statement type is unknown
    """
    type = get_required(data, KEY_TYPE, str)

    if type == TYPE_NARRATION:
        return compile_narration_line(data)
    elif type == TYPE_CHARACTER:
        return compile_character_line(data)
    elif type == TYPE_IF:
        return compile_if_block(data)
    elif type == TYPE_OPTION:
        return compile_option_block(data)
    elif type == TYPE_SET:
        return compile_set_statement(data)
    elif type == TYPE_GOTO:
        return compile_goto_statement(data)
    elif type == TYPE_FINISH:
        return compile_finish_statement(data)
    elif type == TYPE_COMMAND:
        return compile_command_statement(data)
    else:
        raise ValueError(f"Unknown statement type: {type}")


def compile_narration_line(data: dict[str, Any]) -> NarrationLine:
    """Compile a narration line statement.

    Args:
        data: Dictionary containing 'text' field

    Returns:
        NarrationLine statement
    """
    text = get_required(data, KEY_TEXT, str)
    return NarrationLine(text)


def compile_character_line(data: dict[str, Any]) -> CharacterLine:
    """Compile a character dialog line statement.

    Args:
        data: Dictionary containing 'id' (character name) and 'text' fields

    Returns:
        CharacterLine statement
    """
    id = get_required(data, KEY_ID, str)
    text = get_required(data, KEY_TEXT, str)
    return CharacterLine(text=text, id=id)


def compile_set_statement(data: dict[str, Any]) -> SetStatement:
    """Compile a variable assignment statement.

    Args:
        data: Dictionary containing 'id' (variable name) and 'expression' fields

    Returns:
        SetStatement object
    """
    id: str = get_required(data, KEY_ID, str)
    expression: Expression = compile_expression(get_required(data, KEY_EXPRESSION))
    return SetStatement(id, expression)


def compile_goto_statement(data: dict[str, Any]) -> GotoStatement:
    """Compile a goto statement for jumping to another node.

    Args:
        data: Dictionary containing 'id' (target node name)

    Returns:
        GotoStatement object
    """
    id: str = get_required(data, KEY_ID, str)
    return GotoStatement(id)


def compile_finish_statement(data: dict[str, Any]) -> FinishStatement:
    """Compile a finish statement to end dialog execution.

    Args:
        data: Dictionary (no fields required for finish statement)

    Returns:
        FinishStatement object
    """
    return FinishStatement()


def compile_command_statement(data: dict[str, Any]) -> CommandStatement:
    """Compile a command statement for game actions.

    Args:
        data: Dictionary containing 'id' (command name) and 'text' fields

    Returns:
        CommandStatement object
    """
    id: str = get_required(data, KEY_ID, str)
    text: str = get_required(data, KEY_TEXT, str)
    return CommandStatement(id, text)


# =====================
# If Block
# =====================


def compile_if_block(data: dict[str, Any]) -> IfBlock:
    """Compile an if/elif/else conditional block.

    Args:
        data: Dictionary containing 'cases' field with list of if cases

    Returns:
        IfBlock object containing all cases
    """
    cases_data: list[dict[str, Any]] = get_required(data, KEY_CASES, list)
    cases: list[IfCase] = []
    for case_data in cases_data:
        cases.append(compile_if_case(case_data))
    return IfBlock(cases)


def compile_if_case(data: dict[str, Any]) -> IfCase:
    """Compile a single case within an if block.

    Args:
        data: Dictionary containing 'condition' expression and 'body' statements

    Returns:
        IfCase object
    """
    condition: Expression = compile_expression(get_required(data, KEY_CONDITION))
    body: list[Statement] = compile_statements(get_required(data, KEY_BODY, list))
    return IfCase(condition, body)


# =====================
# Option Block
# =====================


def compile_option_block(data: dict[str, Any]) -> OptionBlock:
    """Compile a block of user-selectable options.

    Args:
        data: Dictionary containing 'options' field with list of option definitions

    Returns:
        OptionBlock object containing all options
    """
    options_data: list[dict[str, Any]] = get_required(data, KEY_OPTIONS, list)
    options: list[Option] = []
    for option_data in options_data:
        options.append(compile_option(option_data))
    return OptionBlock(options)


def compile_option(data: dict[str, Any]) -> Option:
    """Compile a single selectable option.

    Args:
        data: Dictionary containing 'condition', 'text', and 'body' fields

    Returns:
        Option object
    """
    condition: Expression = compile_expression(get_required(data, KEY_CONDITION))
    text: str = get_required(data, KEY_TEXT, str)
    body: list[Statement] = compile_statements(get_required(data, KEY_BODY, list))
    return Option(condition, text, body)


# =====================
# Expressions
# =====================


def compile_expression(data: Any) -> Expression:
    """Compile an expression from JSON data.

    Handles boolean literals, numbers, strings, variables, and operators.

    Args:
        data: Expression data (bool, float, str, or dict)

    Returns:
        Expression object of the appropriate type

    Raises:
        ValueError: If expression type is unknown
    """
    if isinstance(data, bool) and bool(data):
        return TrueExpression()

    if isinstance(data, bool) and not bool(data):
        return FalseExpression()

    if isinstance(data, float):
        return Number(float(data))

    if isinstance(data, str):
        return String(str(data))

    if isinstance(data, dict) and KEY_VARIABLE in data:
        variable = get_required(data, KEY_VARIABLE, str)
        return Variable(variable)

    if isinstance(data, dict) and KEY_EXPRESSION in data:
        op = get_required(data, KEY_OP, str)
        expression = compile_expression(get_required(data, KEY_EXPRESSION))
        return UnaryExpression(op, expression)

    if isinstance(data, dict) and KEY_LEFT in data and KEY_RIGHT in data:
        op = get_required(data, KEY_OP, str)
        left = compile_expression(get_required(data, KEY_LEFT))
        right = compile_expression(get_required(data, KEY_RIGHT))
        return BinaryExpression(op, left, right)

    raise ValueError(f"Unknown expression type: {data}")
