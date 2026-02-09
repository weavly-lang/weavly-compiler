from typing import Any

from lark import Transformer, v_args


@v_args(inline=True)
class WenvlTransformer(Transformer):
    def start(self, *children) -> dict[str, list]:
        return {"declarations": list(children)}

    def string_declaration(self, name: str, value: str | None) -> dict[str, str]:
        if value == None:
            value = ""
        return {"type": "string", "name": name, "value": value}
    
    def number_declaration(self, name: str, min: float | None, max: float | None,  value: float | None) -> dict[str, str]:
        if value == None:
            value = 0.0
        return {"type": "number", "name": name, "value": value, "min": min, "max": max}
    
    def flag_declaration(self, name: str, value: bool | None) -> dict[str, str]:
        if value == None:
            value = False
        return {"type": "flag", "name": name, "value": value}

    def STRING(self, token):
        return token[1:-1]
    
    def NUMBER(self, token):
        return float(token)
    
    def TRUE(self, token):
        return True
    
    def FALSE(self, token):
        return False