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

Variables defined outside `.wvl`, as Godot resources or by game code, are declared with `extern` and a type, without a default, min or max. They're written to `env.json` with `"extern": true` and no `value`:

```
@env
score: number = 0
extern reputation: number
@endenv
```

Every variable a script uses must be declared, in expressions, as the target of `@set`, `@increase`, `@decrease`, `@setflag` and `@clearflag`, as a character line's `$name`, and as `{$name}` in line, option, hint and continue text. The build also checks types:

- `+ - * /`, unary `-` and random weights need numbers; `and`, `or` and `not` need flags.
- Comparisons need both sides of the same type.
- Conditions (`@if`, `@elif`, `@when`, option, hint and case conditions) must be flags.
- `@set` must match the variable's type, `@increase` and `@decrease` need a number variable, `@setflag` and `@clearflag` a flag variable, and a character line's `$name` a string variable.
- `visited()` is a flag, `visit_count()` and the other built-in functions are numbers, and built-in function arguments are numbers.

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
