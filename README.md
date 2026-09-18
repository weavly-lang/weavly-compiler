# Weavly Compiler

Compiler for the Weavly dialog scripting language. Parses `.wvl` files and compiles them to JSON for the Weavly Godot runtime.

Language documentation: https://weavly-lang.github.io/weavly-docs/

## Install

Requires Python 3.11+.

```bash
git clone https://github.com/weavly-lang/compiler.git
cd compiler
uv pip install -e .
```

## Usage

```bash
weavly init my-project   # creates my-project/src/nodes.wvl
cd my-project
weavly build             # compiles src/**/*.wvl into build/
weavly build --pretty    # same, with indented JSON
```

`weavly init` without a name sets up `src/` in the current directory.

The build writes:

- `build/<path>.wvl.json` for each source file, containing its nodes
- `build/env.json` with every `@env` declaration in the project

Syntax errors, duplicate variable declarations, duplicate node ids and `@goto` targets with no matching node fail the build with exit code 1. A failed build leaves the previous `build/` untouched.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
