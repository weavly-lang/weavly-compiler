import json
from typing import Any

from lark import Transformer, v_args
from lark.visitors import Discard

located = v_args(inline=True, meta=True)


class InvalidStringError(ValueError):
    def __init__(self, token: Any, reason: str) -> None:
        super().__init__(reason)
        self.token = token
        self.reason = reason


@v_args(inline=True)
class WvlTransformer(Transformer):
    # =====================
    # Entry / Nodes
    # =====================

    def start(self, *children) -> dict[str, list]:
        nodes = [child for child in children if isinstance(child, dict)]
        declarations = [
            decl for child in children if isinstance(child, list) for decl in child
        ]
        result: dict[str, list] = {"nodes": nodes}
        if declarations:
            result["declarations"] = declarations
        return result

    @located
    def node(
        self, meta: Any, node_start: str, meta_block: list | None, body: list, _node_end: None
    ) -> dict[str, Any]:
        node = {"id": node_start, "line": meta.line}
        if meta_block is not None:
            node["meta"] = self._resolve_meta(node_start, meta_block)
        node["body"] = body
        return node

    def _resolve_meta(self, node_id: str, entries: list) -> dict[str, Any]:
        resolved = {}
        once = None
        for key, line, values in entries:
            if key == "once":
                once = (line, values[0])
            elif key in ("pool", "slot"):
                resolved[key] = {"line": line, "value": values}
            else:
                resolved[key] = {"line": line, "value": values[0]}

        if once is not None and once[1] is True:
            not_visited = {"op": "not", "expression": {"call": "visited", "node": node_id}}
            if "when" in resolved:
                when = resolved["when"]
                when["value"] = {"op": "and", "left": when["value"], "right": not_visited}
            else:
                resolved["when"] = {"line": once[0], "value": not_visited}
        return resolved

    # =====================
    # Env Block
    # =====================

    def env_block(self, *declarations) -> list:
        return list(declarations)

    def string_declaration(self, name: str, value: str | None = None) -> dict[str, str]:
        if value is None:
            value = ""
        return {"type": "string", "name": name, "value": str(value)}

    def number_declaration(
        self,
        name: str,
        minimum: float | None,
        maximum: float | None,
        value: float | None,
    ) -> dict[str, Any]:
        if value is None:
            value = 0.0
        return {"type": "number", "name": name, "value": value, "min": minimum, "max": maximum}

    def flag_declaration(self, name: str, value: bool | None = None) -> dict[str, Any]:
        if value is None:
            value = False
        return {"type": "flag", "name": name, "value": bool(value)}

    def name_declaration(self, name: str, value_type: str, value: str) -> dict[str, str]:
        return {"type": value_type, "name": name, "value": value}

    def extern_declaration(self, name: str, value_type: str) -> dict[str, Any]:
        return {"type": value_type, "name": name, "extern": True}

    def value_type(self, token: Any) -> str:
        return str(token)

    def name_type(self, token: Any) -> str:
        return str(token)

    def pool_declaration(self, name: str) -> dict[str, str]:
        return {"kind": "pool", "name": name}

    def slot_declaration(self, name: str) -> dict[str, str]:
        return {"kind": "slot", "name": name}

    def meta_declaration(self, name: str, default: tuple[str, Any]) -> dict[str, Any]:
        value_type, value = default
        return {"kind": "meta", "type": value_type, "name": name, "value": value}

    def number_default(self, value: float | None) -> tuple[str, float]:
        return ("number", 0.0 if value is None else value)

    def string_default(self, value: str | None) -> tuple[str, str]:
        return ("string", "" if value is None else value)

    def flag_default(self, value: bool | None) -> tuple[str, bool]:
        return ("flag", bool(value))

    def name_default(self, value_type: str, value: str) -> tuple[str, str]:
        return (value_type, value)

    def function_declaration(
        self, name: str, parameters: list | None, returns: str
    ) -> dict[str, Any]:
        return {"kind": "function", "name": name, "params": parameters or [], "returns": returns}

    def command_declaration(self, name: str, parameters: list | None) -> dict[str, Any]:
        return {"kind": "command", "name": name, "params": parameters or []}

    def parameters(self, *parameters) -> list:
        return list(parameters)

    def parameter(self, name: str, value_type: str) -> dict[str, str]:
        return {"name": name, "type": value_type}

    def node_start(self, id: str) -> str:
        return id

    def node_end(self) -> None:
        return None

    # =====================
    # Meta Block
    # =====================

    def meta_block(self, *entries) -> list:
        return list(entries)

    @located
    def meta_entry(self, meta: Any, key: str, *values) -> tuple[str, int, list]:
        return (key, meta.line, list(values))

    def body(self, *statements) -> list:
        return list(statements)

    @located
    def inline_jump(self, meta: Any, id: str) -> dict[str, Any]:
        return self.jump(meta, id)

    def action(self, statement_or_body: dict | list) -> list:
        if isinstance(statement_or_body, list):
            return statement_or_body
        return [statement_or_body]

    # =====================
    # Lines / Statements
    # =====================

    @located
    def narration_line(self, meta: Any, text: list) -> dict[str, Any]:
        return {"type": "narration", "line": meta.line, "text": text}

    @located
    def character_line(self, meta: Any, var: dict, text: list) -> dict[str, Any]:
        return {
            "type": "character",
            "line": meta.line,
            "name": var["variable"],
            "name_is_id": True,
            "text": text,
        }

    @located
    def named_character_line(self, meta: Any, name: str, text: list) -> dict[str, Any]:
        return {
            "type": "character",
            "line": meta.line,
            "name": name,
            "name_is_id": False,
            "text": text,
        }

    def blank_line(self) -> Any:
        return Discard

    @located
    def set(self, meta: Any, variable: dict, expression: Any) -> dict[str, Any]:
        return {
            "type": "set",
            "line": meta.line,
            "id": variable["variable"],
            "expression": expression,
        }

    @located
    def increase(self, meta: Any, var: dict, amount: float | None) -> dict[str, Any]:
        return self._change(meta, var, "+", amount)

    @located
    def decrease(self, meta: Any, var: dict, amount: float | None) -> dict[str, Any]:
        return self._change(meta, var, "-", amount)

    def _change(self, meta: Any, var: dict, op: str, amount: float | None) -> dict[str, Any]:
        if amount is None:
            amount = 1.0
        expression = {"op": op, "left": {"variable": var["variable"]}, "right": amount}
        return self.set(meta, var, expression)

    @located
    def setflag(self, meta: Any, var: dict) -> dict[str, Any]:
        return self.set(meta, var, True)

    @located
    def clearflag(self, meta: Any, var: dict) -> dict[str, Any]:
        return self.set(meta, var, False)

    @located
    def jump(self, meta: Any, id: str) -> dict[str, Any]:
        return {"type": "jump", "line": meta.line, "id": id}

    @located
    def detour(self, meta: Any, id: str) -> dict[str, Any]:
        return {"type": "detour", "line": meta.line, "id": id}

    @located
    def draw(self, meta: Any, *pools: str) -> dict[str, Any]:
        return {"type": "draw", "line": meta.line, "pools": list(pools)}

    @located
    def finish(self, meta: Any) -> dict[str, Any]:
        return {"type": "finish", "line": meta.line}

    @located
    def command(self, meta: Any, id: str, arguments: list | None) -> dict[str, Any]:
        return {"type": "command", "line": meta.line, "id": id, "args": arguments or []}

    @located
    def continue_(
        self, meta: Any, text: list, statement: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body = [] if statement is None else [statement]
        return self.option_block(meta, self.option(meta, None, text, body))

    # =====================
    # If Block
    # =====================

    @located
    def if_block(
        self, meta: Any, if_: dict, elif_list: list | None, else_: dict | None
    ) -> dict[str, Any]:
        cases = [if_]
        if elif_list is not None:
            cases.extend(elif_list)
        if else_ is not None:
            cases.append(else_)
        return {"type": "match", "line": meta.line, "modifier": "first", "cases": cases}

    @located
    def if_(self, meta: Any, condition: Any, body: list) -> dict[str, Any]:
        return {"line": meta.line, "condition": condition, "body": body}

    @located
    def elif_(self, meta: Any, condition: Any, body: list) -> dict[str, Any]:
        return self.if_(meta, condition, body)

    @located
    def else_(self, meta: Any, body: list) -> dict[str, Any]:
        return self.if_(meta, True, body)

    def elif_list(self, *elifs) -> list:
        return list(elifs)

    # =====================
    # Option Block
    # =====================

    @located
    def option_block(self, meta: Any, *items) -> dict[str, Any]:
        return {"type": "option", "line": meta.line, "items": list(items)}

    @located
    def option(
        self, meta: Any, condition: Any | None, text: list, body: list
    ) -> dict[str, Any]:
        option_meta = {"label": {"line": meta.line, "value": text}}
        if condition is not None:
            option_meta["when"] = {"line": meta.line, "value": condition}
        return {"type": "inline", "line": meta.line, "meta": option_meta, "body": body}

    @located
    def node_option(self, meta: Any, id: str) -> dict[str, Any]:
        return {"type": "node", "line": meta.line, "id": id}

    @located
    def pool_option(self, meta: Any, *arguments: str | tuple) -> dict[str, Any]:
        parameters = dict(argument for argument in arguments if isinstance(argument, tuple))
        return {
            "type": "pool",
            "line": meta.line,
            "pools": [argument for argument in arguments if isinstance(argument, str)],
            "limit": parameters.get("limit"),
            "shuffle": parameters.get("shuffle", True),
            "locked": parameters.get("locked", "show"),
        }

    def pool_name(self, name: str) -> str:
        return name

    def pool_parameter(self, name: str, value: Any) -> tuple[str, Any]:
        return (name, value)

    # =====================
    # Random Block
    # =====================

    @located
    def random_block(self, meta: Any, *cases) -> dict[str, Any]:
        return {"type": "random", "line": meta.line, "cases": list(cases)}

    @located
    def case(
        self, meta: Any, condition: Any | None, weight: Any, body: list
    ) -> dict[str, Any]:
        if condition is None:
            condition = True
        if weight is None:
            weight = 1.0
        return {"line": meta.line, "condition": condition, "weight": weight, "body": body}

    # =====================
    # Match Block
    # =====================

    @located
    def match_block(self, meta: Any, modifier, *cases) -> dict[str, Any]:
        if modifier is None:
            modifier = "first"
        return {"type": "match", "line": meta.line, "modifier": modifier, "cases": list(cases)}

    def MATCH_MODIFIER(self, token: Any) -> str:
        return str(token)

    @located
    def when(self, meta: Any, condition: Any, body: list) -> dict[str, Any]:
        return {"line": meta.line, "condition": condition, "body": body}

    # =====================
    # Expressions
    # =====================

    def condition(self, expression: Any) -> Any:
        return expression

    def or_(self, left: Any, right: Any) -> dict[str, Any]:
        return {"op": "or", "left": left, "right": right}

    def and_(self, left: Any, right: Any) -> dict[str, Any]:
        return {"op": "and", "left": left, "right": right}

    def not_(self, expression: Any) -> dict[str, Any]:
        return {"op": "not", "expression": expression}

    def compare(self, left: Any, operator: str, right: Any) -> dict[str, Any]:
        return {"op": operator, "left": left, "right": right}

    def add(self, left: Any, right: Any) -> dict[str, Any]:
        return {"op": "+", "left": left, "right": right}

    def sub(self, left: Any, right: Any) -> dict[str, Any]:
        return {"op": "-", "left": left, "right": right}

    def negative_number(self, number: float) -> float:
        return -number

    def neg(self, operand: Any) -> Any:
        if isinstance(operand, float):
            return -operand
        return {"op": "-", "left": 0.0, "right": operand}

    def mul(self, left: Any, right: Any) -> dict[str, Any]:
        return {"op": "*", "left": left, "right": right}

    def div(self, left: Any, right: Any) -> dict[str, Any]:
        return {"op": "/", "left": left, "right": right}

    def variable(self, id: str) -> dict[str, str]:
        return {"variable": id}

    def name(self, id: str) -> str:
        return id

    def node_call(self, function: str, node: str) -> dict[str, str]:
        return {"call": function, "node": node}

    def meta_call(self, node: str, key: str) -> dict[str, str]:
        return {"call": "meta", "node": node, "key": key}

    def call(self, function: str, arguments: list | None) -> dict[str, Any]:
        return {"call": function, "args": arguments or []}

    def arguments(self, *expressions) -> list:
        return list(expressions)

    # =====================
    # Text
    # =====================

    def text(self, *segments) -> list:
        return list(segments)

    def interpolation(self, expression: Any) -> Any:
        return expression

    # =====================
    # Tokens
    # =====================

    def CHARACTER_NAME(self, token: Any) -> str:
        return str(token).strip()

    def COMP_OP(self, token: Any) -> str:
        return str(token)

    def TRUE(self, token: Any) -> bool:
        return True

    def FALSE(self, token: Any) -> bool:
        return False

    def ID(self, token: Any) -> str:
        return str(token)

    def NUMBER(self, token: Any) -> float:
        return float(token)

    def STRING(self, token: Any) -> str:
        try:
            return json.loads(str(token), strict=False)
        except json.JSONDecodeError as e:
            raise InvalidStringError(token, e.msg) from e

    # =====================
    # Default for debugging
    # =====================

    def __default__(self, data: str, children: list, meta: Any) -> None:
        # raise here to catch unhandled rules early
        raise ValueError(f"Unhandled rule: {data} children={children}")
