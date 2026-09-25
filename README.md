# Weavly Compiler

Compiler for the Weavly dialogue scripting language. Parses `.wvl` files and compiles them to JSON for the Weavly Godot runtime.

Language documentation: https://weavly-lang.github.io/weavly-docs/

## Install

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
uv tool install weavly
```

uv installs a suitable Python if needed and puts `weavly` on your PATH (run `uv tool update-shell` if it isn't). Upgrade with `uv tool upgrade weavly`.

With Python 3.11+ already installed, `pipx install weavly` works too.

## Usage

```bash
weavly init my-project   # creates my-project/src/nodes.wvl
cd my-project
weavly build             # compiles src/**/*.wvl into build/
weavly build --pretty    # same, with indented JSON
weavly --version         # installed compiler version
```

`weavly init` without a name sets up `src/` in the current directory.

The build writes:

- `build/<path>.wvl.json` for each source file, containing its nodes and a `source` field with the path relative to `src/` (for example `"chapter1/intro.wvl"`). Nodes, statements, match and random cases and option items carry the 1-based `line` they start on, so runtime errors can point back to the `.wvl` source.
- `build/env.json` with every `@env` variable declaration in the project in `declarations`, and the names of all pools and slots in `pools` and `slots`

Commands take comma-separated expressions as arguments and are written with them in `args`, for the game to evaluate when the command runs:

```
@play_sound "door", $volume * 0.5
```

```json
{"type": "command", "line": 1, "id": "play_sound", "args": ["door", {"op": "*", "left": {"variable": "volume"}, "right": 0.5}]}
```

Arguments are checked like any other expression. Command names aren't declared, so the build doesn't check them or how many arguments they get.

Line, character line, option, hint and continue text can hold any expression inside `{}`:

```
The room costs {$base_price * $markup} gold.
@option "Pay {round($price)} gold"
```

`text` is written as a list of plain strings and expressions, for the game to evaluate each expression and join the segments. It's a list even without expressions, and never holds empty strings:

```json
{"type": "narration", "line": 1, "text": ["The room costs ", {"op": "*", "left": {"variable": "base_price"}, "right": {"variable": "markup"}}, " gold."]}
```

Write `\{` for a literal brace. A `}` outside an expression is plain text. String literals inside `{}` in quoted text escape their quotes like any other quote in it: `@option "Greet {$name == \"Bob\"}"`.

Variables defined outside `.wvl`, as Godot resources or by game code, are declared with `extern` and a type, without a default, min or max. They're written to `env.json` with `"extern": true` and no `value`:

```
@env
score: number = 0
extern reputation: number
@endenv
```

Storylets are nodes the game picks from a pool instead of a script naming them. Pools and slots are declared in `@env`, without a default:

```
@env
cave_outcome: pool
treasure: slot
@endenv
```

They share names with variables, so a name can be declared only once in the project, but a node id may match one. A node joins pools with a `@meta` block of `key: value` entries, right after its `@node` line:

```
@node cave_treasure
@meta
pool: cave_outcome
slot: treasure
when: $luck > 5
priority: 1
weight: 2
once: true
@endmeta
You squeeze through the gap...
@endnode
```

- `pool`: comma-separated pool names, at least one.
- `slot`: comma-separated slot names. Nodes sharing a slot exclude each other when the game lists a pool.
- `when`: a flag expression, the node is eligible only while it's true.
- `priority` and `weight`: number expressions. The game defaults them to 0 and 1.
- `once`: `true` adds `not visited(<this node>)` to `when`. It isn't written to the output.

The node gets a `meta` object with the entries that were written, each with its `line` and `value`:

```json
{"id": "cave_treasure", "line": 1, "meta": {
  "pool": {"line": 3, "value": ["cave_outcome"]},
  "slot": {"line": 4, "value": ["treasure"]},
  "when": {"line": 5, "value": {"op": "and", "left": {"op": ">", "left": {"variable": "luck"}, "right": 5.0}, "right": {"op": "not", "expression": {"call": "visited", "node": "cave_treasure"}}}},
  "priority": {"line": 6, "value": 1.0},
  "weight": {"line": 7, "value": 2.0}
}, "body": [...]}
```

A `when` that only comes from `once` carries the `once` line.

`@draw` plays one storylet from one or more comma-separated pools, as a statement or an inline action:

```
@node cave_enter
You search the cave.
@draw cave_outcome
You find nothing of interest.
@endnode
```

```json
{"type": "draw", "line": 3, "pools": ["cave_outcome"]}
```

`pools` is always a list, in the written order. Every pool must be declared, but it can still be without members. The game combines the members of all given pools, counting a node that's in several of them once, and picks the eligible node with the highest priority, with weight deciding between equal priorities. It jumps there like `@goto`. If no node is eligible, execution continues with the next statement, which is where a fallback goes.

Every variable a script uses must be declared, in expressions, as the target of `@set`, `@increase`, `@decrease`, `@setflag` and `@clearflag`, as a character line's `$name`, and in expressions inside `{}` in text. The build also checks types:

- `+ - * /`, unary `-` and random weights need numbers; `and`, `or` and `not` need flags.
- Comparisons need both sides of the same type.
- Conditions (`@if`, `@elif`, `@when`, option, hint and case conditions) must be flags.
- `@set` must match the variable's type, `@increase` and `@decrease` need a number variable, `@setflag` and `@clearflag` a flag variable, and a character line's `$name` a string variable.
- `visited()` is a flag, `visit_count()` and the other built-in functions are numbers, and built-in function arguments are numbers.
- Expressions inside `{}` in text can be of any type.
- `when` must be a flag, `priority` and `weight` numbers, and `once` `true` or `false`. Pools and slots can't be used as `$name`.

Syntax errors, duplicate declarations, number declarations whose min, max or default don't fit together, duplicate node ids, unknown functions, function calls with the wrong number of arguments, `@goto`, `visited()` and `visit_count()` targets with no matching node, undeclared variables, pools and slots, unknown or duplicate `@meta` keys, and type errors fail the build with exit code 1. A failed build leaves the previous `build/` untouched.

## Development

```bash
git clone https://github.com/weavly-lang/weavly-compiler.git
cd weavly-compiler
uv sync --group dev
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and release steps.

## License

[MIT](LICENSE)
