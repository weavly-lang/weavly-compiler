from typing import Any

from lark import Discard, Transformer, v_args


@v_args(inline=True)
class WenvlTransformer(Transformer):
    DEFAULT_STRING = ""
    DEFAULT_NUMBER = 0.0
    DEFAULT_FLAG = False

    def start(self, *children) -> dict[str, list]:
        return {"declarations": list(children)}

    def string_declaration(self, name: str, value=None) -> dict[str, str]:
        if value is None:
            value = self.DEFAULT_STRING
        return {"type": "string", "name": name, "value": str(value)}
    
    def number_declaration(self, name: str, min=None, max=None, value=None) -> dict[str, Any]:
        if value is None:
            value = self.DEFAULT_NUMBER
        return {"type": "number", "name": name, "value": float(value), "min": min, "max": max}
    
    def flag_declaration(self, name: str, value=None) -> dict[str, Any]:
        if value is None:
            value = self.DEFAULT_FLAG
        return {"type": "flag", "name": name, "value": bool(value)}

    def blank_line(self) -> Any:
        return Discard

    def ID(self, token):
        return str(token)

    def STRING(self, token):
        return token[1:-1]
    
    def NUMBER(self, token):
        return float(token)
    
    def TRUE(self, token):
        return True
    
    def FALSE(self, token):
        return False