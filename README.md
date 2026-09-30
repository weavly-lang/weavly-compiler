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
- `build/env.json` with every `@env` variable declaration in the project in `declarations`, the names of all pools and slots in `pools` and `slots`, and custom meta keys in `meta_keys`

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

Every `@env` declaration starts with its kind: `var`, `extern var`, `pool`, `slot` or `meta`. Variables defined outside `.wvl`, as Godot resources or by game code, are declared with `extern var` and a type, without a default, min or max. They're written to `env.json` with `"extern": true` and no `value`:

```
@env
var score: number(0, 100) = 0
extern var reputation: number
@endenv
```

Storylets are nodes the game picks from a pool instead of a script naming them. Pools and slots are declared by name:

```
@env
pool cave_outcome
slot treasure
@endenv
```

Besides `number`, `string` and `flag`, a variable can hold a `node`, `pool` or `slot`. It needs a default, written as a bare name, and `extern var` works with these types too. In expressions, a bare name is such a value: it can be compared with `==` and `!=`, set with `@set` and passed to commands. The build checks that the name exists and has the right type, and writes it as a string, in `env.json` and in expressions:

```
@env
var region: pool = cave_outcome
@endenv

@node camp
@if $region == cave_outcome
    The cave is close.
@endif
@endnode
```

```json
{"type": "pool", "name": "region", "value": "cave_outcome"}
```

`@jump`, `@detour`, `@draw` and `@meta` keys still take names, not variables.

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

Games can attach their own data to a node with custom meta keys, declared in `@env` with a type and an optional default. Defaults work like variable defaults: `number`, `string` and `flag` default to 0, "" and false, and `node`, `pool` and `slot` need one. Custom keys have no range. In `@meta`, a custom key takes one expression of its type, and it's written next to the built-in keys, in the same shape:

```
@env
meta cost: number = 1
meta art: string
@endenv

@node rest_at_camp
@meta
pool: camp
cost: 1 + $fatigue
art: "camp_fire"
@endmeta
@set $energy = $energy - meta(cost)
@endnode
```

`env.json` lists each key in `meta_keys` with its type and default:

```json
{"type": "number", "name": "cost", "value": 1.0}
```

Built-in key names can't be declared, and custom keys share names with variables, pools and slots.

`meta(<key>)` reads a key of the current node, and `meta(<node>, <key>)` reads one of another node. The build writes the current node's id when it's left out: `{"call": "meta", "node": "rest_at_camp", "key": "cost"}`. The game evaluates the value when it's read, and uses the default for a node that doesn't write the key. `meta()` reads custom keys and `when`, `priority` and `weight`. A meta value that reads itself, directly or through other meta values, fails the build.

`skip_count(<node>)` is how often the node was eligible when the game listed or drew from one of its pools, but wasn't taken. The game resets it when the node is taken, so a storylet that keeps being passed over can raise its own chances:

```
@meta
pool: cave_outcome
weight: 1 + skip_count()
@endmeta
```

`visited()`, `visit_count()` and `skip_count()` without an argument mean the node they're written in. The build writes that node's id, as if it had been written out.

`@jump` moves to another node for good. `@detour` runs another node and, when it ends, continues after the `@detour`. `->` is the short form of `@jump` in an inline action, like `@option "Leave" -> road`:

```
@node travel
You set off toward the city.
@detour ambush
You arrive at the gates.
@jump city
@endnode
```

```json
{"type": "detour", "line": 3, "id": "ambush"}
{"type": "jump", "line": 5, "id": "city"}
```

A `@jump` drops every point a detour would return to, including the scenes that detoured or drew into the current node. `@finish` ends the whole dialogue, inside a detour too.

`@draw` plays one storylet from one or more comma-separated pools, as a statement or an inline action. It runs the storylet like a `@detour`:

```
@node cave_enter
You search the cave.
@draw cave_outcome
You climb back out.
@endnode
```

```json
{"type": "draw", "line": 3, "pools": ["cave_outcome"]}
```

`pools` is always a list, in the written order. Every pool must be declared, but it can still be without members. The game combines the members of all given pools, counting a node that's in several of them once, and picks the eligible node with the highest priority, with weight deciding between equal priorities. If no node is eligible, nothing is played. A fallback is a node in the pool with the lowest priority:

```
@node quiet_cave
@meta
pool: cave_outcome
priority: -1
@endmeta
Nothing but dripping water.
@endnode
```

Every variable a script uses must be declared, in expressions, as the target of `@set`, `@increase`, `@decrease`, `@setflag` and `@clearflag`, as a character line's `$name`, and in expressions inside `{}` in text. The build also checks types:

- `+ - * /`, unary `-` and random weights need numbers; `and`, `or` and `not` need flags.
- Comparisons need both sides of the same type.
- Conditions (`@if`, `@elif`, `@when`, option, hint and case conditions) must be flags.
- `@set` must match the variable's type, `@increase` and `@decrease` need a number variable, `@setflag` and `@clearflag` a flag variable, and a character line's `$name` a string variable.
- `visited()` is a flag, `visit_count()`, `skip_count()` and the other built-in functions are numbers, and built-in function arguments are numbers.
- Expressions inside `{}` in text can be of any type.
- `when` must be a flag, `priority` and `weight` numbers, and `once` `true` or `false`. Pools and slots can't be used as `$name`.
- A bare name is a `node`, `pool` or `slot`, and `<`, `>`, `<=` and `>=` can't compare them. A name that is both a node and a pool or slot takes the type the expression needs.

Syntax errors, duplicate declarations, number declarations whose min, max or default don't fit together, duplicate node ids, unknown functions, function calls with the wrong number of arguments, `@jump`, `@detour`, `visited()`, `visit_count()` and `skip_count()` targets with no matching node, undeclared variables, pools and slots, bare names that aren't a node, pool or slot, unknown or duplicate `@meta` keys, `meta()` calls on unknown keys or missing nodes, meta values that read themselves, and type errors fail the build with exit code 1. A failed build leaves the previous `build/` untouched.

## Development

```bash
git clone https://github.com/weavly-lang/weavly-compiler.git
cd weavly-compiler
uv sync --group dev
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and release steps.

## License

[MIT](LICENSE)
