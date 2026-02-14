from typing import Any

from lark import Transformer, v_args
from lark.visitors import Discard


@v_args(inline=True)
class WvlTransformer(Transformer):
    # =====================
    # Entry / Nodes
    # =====================

    def start(self, *children) -> dict[str, list]:
        return {"nodes": list(children)}

    def node(self, node_start: str, body: list, _node_end: None) -> dict[str, Any]:
        return {"id": node_start, "body": body}

    def node_start(self, id: str) -> str:
        return id

    def node_end(self) -> None:
        return None

    def body(self, *statements) -> list:
        return list(statements)

    # =====================
    # Lines / Statements
    # =====================

    def narration_line(self, text: str) -> dict[str, str]:
        return {"type": "narration", "text": text}

    def character_line(self, var: dict, text: str) -> dict[str, str]:
        return {"type": "character", "name": var["variable"], "id": True, "text": text}
    
    def named_character_line(self, name: str, text: str) -> dict[str, str]:
        return {"type": "character", "name": name, "id": False, "text": text}

    def blank_line(self) -> Any:
        return Discard

    def set(self, variable: dict, expression: Any) -> dict[str, Any]:
        return {"type": "set", "id": variable["variable"], "expression": expression}

    def increase(self, var: dict, number: float | None) -> dict[str, Any]:
        if number is None:
            number = 1.0
        expression = {"op": "+", "left": {"variable": var["variable"]}, "right": number}
        return self.set(var, expression)

    def decrease(self, var: dict, number: float | None) -> dict[str, Any]:
        if number is None:
            number = 1.0
        expression = {"op": "-", "left": {"variable": var["variable"]}, "right": number}
        return self.set(var, expression)

    def setflag(self, var: dict) -> dict[str, Any]:
        return self.set(var, True)

    def clearflag(self, var: dict) -> dict[str, Any]:
        return self.set(var, False)

    def goto(self, id: str) -> dict[str, str]:
        return {"type": "goto", "id": id}

    def finish(self) -> dict[str, str]:
        return {"type": "finish"}

    def command(self, id: str, text: str | None) -> dict[str, str]:
        if text is None:
            text = ""
        return {"type": "command", "id": id, "text": text}

    def continue_(self, text: str) -> dict[str, Any]:
        return self.option_block(self.option(None, text, []))

    # =====================
    # If Block
    # =====================

    def if_block(
        self, if_: dict, elif_list: list | None, else_: dict | None
    ) -> dict[str, Any]:
        cases = [if_]
        if elif_list is not None:
            cases.extend(elif_list)
        if else_ is not None:
            cases.append(else_)
        return {"type": "if", "cases": cases}

    def if_(self, condition: Any, body: list) -> dict[str, Any]:
        return {"condition": condition, "body": body}

    def elif_(self, condition: Any, body: list) -> dict[str, Any]:
        return self.if_(condition, body)

    def else_(self, body: list) -> dict[str, Any]:
        return self.if_(True, body)

    def elif_list(self, *elifs) -> list:
        return list(elifs)

    # =====================
    # Option Block
    # =====================

    def option_block(self, *items) -> dict[str, Any]:
        return {"type": "option", "items": list(items)}

    def option(self, condition: Any | None, text: str, body: list, hint: bool = False) -> dict[str, Any]:
        if condition is None:
            condition = True
        return {"condition": condition, "text": text, "body": body, "hint": hint}

    def hint_option(self, condition: Any | None, text: str) -> dict[str, Any]:
        return self.option(condition, text, [], hint=True)
    
    # =====================
    # Random Block
    # =====================

    def random_block(self, *cases) -> dict[str, Any]:
        return {"type": "random", "cases": list(cases)}

    def case(self, condition: Any | None, weight: Any, body: list) -> dict[str, Any]:
        if condition is None:
            condition = True
        return {"condition": condition, "weight": weight, "body": body}

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

    def mul(self, left: Any, right: Any) -> dict[str, Any]:
        return {"op": "*", "left": left, "right": right}

    def div(self, left: Any, right: Any) -> dict[str, Any]:
        return {"op": "/", "left": left, "right": right}

    def variable(self, id: str) -> dict[str, str]:
        return {"variable": id}

    # =====================
    # Tokens
    # =====================

    def TEXT(self, token: Any) -> str:
        return str(token).lstrip()
    
    def CHARACTER_NAME(self, token: Any) -> str:
        return str(token).lstrip()

    def OPTIONTEXT(self, token: Any) -> str:
        return str(token).lstrip()

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
        return str(token)

    # =====================
    # Default for debugging
    # =====================

    def __default__(self, data: str, children: list, meta: Any) -> None:
        # raise here to catch unhandled rules early
        raise ValueError(f"Unhandled rule: {data} children={children}")
