from pathlib import Path

from lark import Token, Tree

from .checks import DECLARATION_KINDS, entry_names, node_meta
from .type_checker import Location, source_location

# rule -> the kind of declaration its leading name uses.
_USES = {"variable": "variable", "call": "function", "command": "command"}
_POOL_ONLY_KEYS = ("priority", "weight", "slot")


def find_warnings(trees: list[tuple[Path, Tree]]) -> list[tuple[Location, str]]:
    """Return warnings for declarations and meta keys that can't have an effect."""
    declared: list[tuple[str, Token, Path]] = []
    used: dict[str, set[str]] = {kind: set() for kind in DECLARATION_KINDS.values()}
    # "pool" or "slot" -> name -> the node ids that join it.
    members: dict[str, dict[str, set[str]]] = {"pool": {}, "slot": {}}
    warnings: list[tuple[Location, str]] = []

    for file, tree in trees:
        for subtree in tree.iter_subtrees_topdown():
            if subtree.data in DECLARATION_KINDS:
                declared.append((DECLARATION_KINDS[subtree.data], subtree.children[0], file))
            elif subtree.data in _USES:
                used[_USES[subtree.data]].add(str(subtree.children[0]))
            elif subtree.data == "meta_call":
                used["meta key"].add(str(subtree.children[1]))

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
    return warnings


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
