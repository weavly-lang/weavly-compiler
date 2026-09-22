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

- `build/<path>.wvl.json` for each source file, containing its nodes
- `build/env.json` with every `@env` declaration in the project

Syntax errors, duplicate variable declarations, number declarations whose min, max or default don't fit together, duplicate node ids and `@goto` targets with no matching node fail the build with exit code 1. A failed build leaves the previous `build/` untouched.

## Development

```bash
git clone https://github.com/weavly-lang/weavly-compiler.git
cd weavly-compiler
uv sync --group dev
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and release steps.

## License

[MIT](LICENSE)
