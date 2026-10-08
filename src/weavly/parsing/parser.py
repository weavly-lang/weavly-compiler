from functools import cache
from importlib import resources

from lark import Lark, Token, Tree

from .text import expand_text
from .type_checker import NODE_FUNCTIONS
from .wvl_transformer import WvlTransformer

GRAMMAR_FILE = "wvl-grammar.lark"


@cache
def create_parser() -> Lark:
    grammar = resources.files("weavly.resources").joinpath(GRAMMAR_FILE).read_text("utf-8")
    return Lark(
        grammar,
        parser="lalr",
        propagate_positions=True,
        start=["start", "interpolation"],
    )


def parse(text: str) -> Tree:
    """Parse `text` into a tree whose text and node function calls are resolved."""
    parser = create_parser()
    tree = parser.parse(text, start="start")
    expand_text(tree, parser)
    _resolve_node_calls(tree)
    return tree


def compile_source(text: str) -> dict:
    return WvlTransformer().transform(parse(text))


def _resolve_node_calls(tree: Tree) -> None:
    """Turn node function calls on names and meta reads into node and meta calls, filling in
    the enclosing node when it's left out."""
    for node in tree.find_data("node"):
        node_id = node.children[0].children[0]
        for call in node.find_data("call"):
            function, arguments = call.children
            names = _names(arguments)
            if function in NODE_FUNCTIONS and names is not None and len(names) <= 1:
                current = Token.new_borrow_pos("ID", node_id, function)
                call.data = "node_call"
                call.children = [function, *(names or [current])]
        for read in node.find_data("meta_read"):
            token = read.children[0]
            target, key = token.split(".")
            read.data = "meta_call"
            read.children = [
                _part(token, target, 0) if target else Token.new_borrow_pos("ID", node_id, token),
                _part(token, key, len(target) + 1),
            ]


def _part(token: Token, value: str, offset: int) -> Token:
    """Return the part of `token` that starts `offset` characters into it as an ID."""
    part = Token.new_borrow_pos("ID", value, token)
    part.column += offset
    part.end_column = part.column + len(value)
    return part


def _names(arguments: Tree | None) -> list[Token] | None:
    """Return the names `arguments` consists of, or None if any argument isn't a name."""
    items = [] if arguments is None else arguments.children
    if not all(isinstance(item, Tree) and item.data == "name" for item in items):
        return None
    return [item.children[0] for item in items]
