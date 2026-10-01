# Weavly Compiler

Compiles Weavly dialogue scripts (`.wvl`) to JSON for the [Weavly Godot addon](https://github.com/weavly-lang/weavly-godot-addon).

Weavly is in alpha. The language and the JSON output change between releases without backward compatibility, so use the addon release that matches your compiler version.

## Install

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
uv tool install weavly
```

Upgrade with `uv tool upgrade weavly`. With Python 3.11+ installed, `pipx install weavly` works too.

## Usage

```bash
weavly init my-project   # creates my-project/src/nodes.wvl
cd my-project
weavly build             # compiles src/**/*.wvl into build/
weavly build --pretty    # same, with indented JSON
weavly --version
```

The build writes one `build/<path>.wvl.json` per source file and a merged `build/env.json` with every declaration of the project. Errors are printed as `file:line:column: error: ...` and fail the build with exit code 1, leaving the previous `build/` untouched. Warnings use the same format and don't fail the build.

## Development

```bash
git clone https://github.com/weavly-lang/weavly-compiler.git
cd weavly-compiler
uv sync --group dev
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
