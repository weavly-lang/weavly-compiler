from functools import cache
from importlib import resources

from lark import Lark, Token, Tree

from .text import expand_text
from .type_checker import META_FUNCTION, NODE_FUNCTIONS
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
    """Turn node function and meta() calls on names into node and meta calls, filling in the
    enclosing node when it's left out."""
    for node in tree.find_data("node"):
        node_id = node.children[0].children[0]
        for call in node.find_data("call"):
            function, arguments = call.children
            names = _names(arguments)
            if names is None:
                continue
            current = Token.new_borrow_pos("ID", node_id, function)
            if function in NODE_FUNCTIONS and len(names) <= 1:
                call.data = "node_call"
                call.children = [function, *(names or [current])]
            elif function == META_FUNCTION and len(names) in (1, 2):
                call.data = "meta_call"
                call.children = names if len(names) == 2 else [current, *names]


def _names(arguments: Tree | None) -> list[Token] | None:
    """Return the names `arguments` consists of, or None if any argument isn't a name."""
    items = [] if arguments is None else arguments.children
    if not all(isinstance(item, Tree) and item.data == "name" for item in items):
        return None
    return [item.children[0] for item in items]
