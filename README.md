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
- `build/env.json` with every `@env` declaration in the project

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

Every variable a script uses must be declared, in expressions, as the target of `@set`, `@increase`, `@decrease`, `@setflag` and `@clearflag`, as a character line's `$name`, and in expressions inside `{}` in text. The build also checks types:

- `+ - * /`, unary `-` and random weights need numbers; `and`, `or` and `not` need flags.
- Comparisons need both sides of the same type.
- Conditions (`@if`, `@elif`, `@when`, option, hint and case conditions) must be flags.
- `@set` must match the variable's type, `@increase` and `@decrease` need a number variable, `@setflag` and `@clearflag` a flag variable, and a character line's `$name` a string variable.
- `visited()` is a flag, `visit_count()` and the other built-in functions are numbers, and built-in function arguments are numbers.
- Expressions inside `{}` in text can be of any type.

Syntax errors, duplicate variable declarations, number declarations whose min, max or default don't fit together, duplicate node ids, unknown functions, function calls with the wrong number of arguments, `@goto`, `visited()` and `visit_count()` targets with no matching node, undeclared variables, and type errors fail the build with exit code 1. A failed build leaves the previous `build/` untouched.

## Development

```bash
git clone https://github.com/weavly-lang/weavly-compiler.git
cd weavly-compiler
uv sync --group dev
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and release steps.

## License

[MIT](LICENSE)
