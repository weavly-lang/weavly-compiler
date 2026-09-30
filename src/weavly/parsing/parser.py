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
    """Turn node function calls on a name, or without one for the enclosing node, into node calls."""
    for node in tree.find_data("node"):
        node_id = node.children[0].children[0]
        for call in node.find_data("call"):
            function, arguments = call.children
            if function not in NODE_FUNCTIONS:
                continue
            if arguments is None:
                target = Token.new_borrow_pos("ID", node_id, function)
            elif len(arguments.children) == 1 and _is_name(arguments.children[0]):
                target = arguments.children[0].children[0]
            else:
                continue
            call.data = "node_call"
            call.children = [function, target]


def _is_name(item: Tree | Token) -> bool:
    return isinstance(item, Tree) and item.data == "name"
