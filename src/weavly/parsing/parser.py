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
    """Parse `text` into a tree whose text and current-node calls are resolved."""
    parser = create_parser()
    tree = parser.parse(text, start="start")
    expand_text(tree, parser)
    _resolve_current_node(tree)
    return tree


def compile_source(text: str) -> dict:
    return WvlTransformer().transform(parse(text))


def _resolve_current_node(tree: Tree) -> None:
    """Turn node function calls without an argument into calls on their enclosing node."""
    for node in tree.find_data("node"):
        node_id = node.children[0].children[0]
        for call in node.find_data("call"):
            function, arguments = call.children
            if function in NODE_FUNCTIONS and arguments is None:
                call.data = "node_call"
                call.children = [function, Token.new_borrow_pos("ID", node_id, function)]
