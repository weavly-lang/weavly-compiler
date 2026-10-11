import re
from pathlib import Path

from lark import Token, Tree

from .checks import DECLARATION_KINDS, entry_names, node_meta
from .text import blank_strings
from .type_checker import Location, source_location

# rule -> the kind of declaration its leading name uses.
_USES = {
    "variable": "variable",
    "set": "variable",
    "increase": "variable",
    "decrease": "variable",
    "call": "function",
    "do": "function",
    "name": "character",
    "character_speaker": "character",
}
_POOL_ONLY_KEYS = ("priority", "weight", "slot")
_IGNORE = re.compile(r"#[ \t]*weavly:[ \t]*ignore[ \t]*$")
# file -> line -> column of its `# weavly: ignore` comment.
Ignores = dict[Path, dict[int, int]]


def find_ignores(text: str, tree: Tree) -> dict[int, int]:
    """Return line -> column of every `# weavly: ignore` comment in `text`, which parses to
    `tree`; on narration and dialogue lines `#` is text."""
    text_lines = {text_tree.meta.line for text_tree in tree.find_data("text")}
    ignores = {}
    for number, line in enumerate(text.splitlines(), start=1):
        if number in text_lines:
            continue
        code = blank_strings(line)
        start = code.find("#")
        if start != -1 and _IGNORE.match(code, start):
            ignores[number] = start + 1
    return ignores


def find_warnings(
    trees: list[tuple[Path, Tree]], ignores: Ignores
) -> list[tuple[Location, str]]:
    """Return warnings for declarations and meta keys that can't have an effect, without the
    ones `ignores` silences, and for every ignore that silences nothing."""
    declared: list[tuple[str, Token, Path]] = []
    used: dict[str, set[str]] = {kind: set() for kind in DECLARATION_KINDS.values()}
    # "pool" or "slot" -> name -> the node ids that join it.
    members: dict[str, dict[str, set[str]]] = {"pool": {}, "slot": {}}
    warnings: list[tuple[Location, str]] = []

    for file, tree in trees:
        for subtree in tree.iter_subtrees_topdown():
            if subtree.data in DECLARATION_KINDS:
                declared.append((DECLARATION_KINDS[subtree.data], subtree.children[0], file))
            elif subtree.data in _USES and isinstance(subtree.children[0], Token):
                used[_USES[subtree.data]].add(str(subtree.children[0]))
            elif subtree.data == "meta_call":
                used["meta key"].add(str(subtree.children[1]))
            elif subtree.data == "name_value":
                used["character"].add(str(subtree.children[1]))
            elif subtree.data == "var_argument" and isinstance(subtree.children[0], Tree):
                used["variable"].add(str(subtree.children[0].children[0]))
            elif subtree.data == "narration_line" and subtree.children[1] is not None:
                text, colon = subtree.children
                warnings.append((source_location(file, colon), _looks_like_dialogue(text, colon)))

        for node_id, entries in node_meta(tree):
            used["meta key"].update(entries)
            for kind, names in members.items():
                for name in entry_names(entries.get(kind)):
                    names.setdefault(name, set()).add(node_id)
            if "pool" in entries:
                continue
            for key in _POOL_ONLY_KEYS:
                if key in entries:
                    location = source_location(file, entries[key].children[0])
                    warnings.append((location, f"{key} has no effect on a node in no pool"))

    for kind, name, file in declared:
        message = _unused(kind, str(name), used, members)
        if message:
            warnings.append((source_location(file, name), message))
    return _apply_ignores(warnings, ignores)


def _apply_ignores(
    warnings: list[tuple[Location, str]], ignores: Ignores
) -> list[tuple[Location, str]]:
    kept = []
    silenced: set[tuple[Path, int]] = set()
    for location, message in warnings:
        file, line, _ = location
        if line in ignores.get(file, {}):
            silenced.add((file, line))
        else:
            kept.append((location, message))
    for file, lines in ignores.items():
        kept.extend(
            ((file, line, column), "weavly: ignore silences no warning")
            for line, column in lines.items()
            if (file, line) not in silenced
        )
    return kept


def _looks_like_dialogue(text: Tree, colon: Token) -> str:
    first = text.children[0]
    expression = first.children[0] if isinstance(first, Tree) else None
    if (
        isinstance(expression, Tree)
        and expression.data in ("name", "variable")
        and first.meta.end_column == colon.column
    ):
        speaker = expression.children[0]
        return (
            f'this line looks like dialogue: write {speaker}: or "{{{speaker}}}": '
            "for a speaker, or \\: for narration"
        )
    return "this line looks like dialogue: quote the speaker or write \\: for narration"


def _unused(
    kind: str, name: str, used: dict[str, set[str]], members: dict[str, dict[str, set[str]]]
) -> str | None:
    if kind in members:
        count = len(members[kind].get(name, ()))
        if count == 0:
            return f"{kind} '{name}' has no nodes"
        if kind == "slot" and count == 1:
            return f"slot '{name}' has only one node"
        return None
    if name in used[kind]:
        return None
    if kind == "meta key":
        return f"meta key '{name}' is never written or read"
    return f"{kind} '{name}' is never used"
