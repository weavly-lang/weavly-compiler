from pathlib import Path

from lark import Token, Tree

from .type_checker import Location, source_location

# declaration rule -> what warnings call it.
_DECLARATIONS = {
    "extern_declaration": "extern variable",
    "function_declaration": "function",
    "command_declaration": "command",
    "meta_declaration": "meta key",
    "pool_declaration": "pool",
    "slot_declaration": "slot",
}
# rule -> the kind of declaration its leading name uses.
_USES = {"variable": "extern variable", "call": "function", "command": "command"}
_POOL_ONLY_KEYS = ("priority", "weight", "slot")


def find_warnings(trees: list[tuple[Path, Tree]]) -> list[tuple[Location, str]]:
    """Return warnings for declarations and meta keys that can't have an effect."""
    declared: list[tuple[str, Token, Path]] = []
    used: dict[str, set[str]] = {kind: set() for kind in _DECLARATIONS.values()}
    # "pool" or "slot" -> name -> the node ids that join it.
    members: dict[str, dict[str, set[str]]] = {"pool": {}, "slot": {}}
    warnings: list[tuple[Location, str]] = []

    for file, tree in trees:
        for subtree in tree.iter_subtrees_topdown():
            if subtree.data in _DECLARATIONS:
                declared.append((_DECLARATIONS[subtree.data], subtree.children[0], file))
            elif subtree.data in _USES:
                used[_USES[subtree.data]].add(str(subtree.children[0]))
            elif subtree.data == "meta_call":
                used["meta key"].add(str(subtree.children[1]))

        for node in tree.find_data("node"):
            node_id = str(node.children[0].children[0])
            entries = {str(entry.children[0]): entry for entry in node.find_data("meta_entry")}
            used["meta key"].update(entries)
            for kind in members:
                for value in entries[kind].children[1:] if kind in entries else []:
                    if isinstance(value, Tree) and value.data == "name":
                        members[kind].setdefault(str(value.children[0]), set()).add(node_id)
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
