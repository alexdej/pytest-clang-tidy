# pytest-clang-tidy

[![CI](https://github.com/alexdej/pytest-clang-tidy/actions/workflows/ci.yml/badge.svg)](https://github.com/alexdej/pytest-clang-tidy/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pytest-clang-tidy)](https://pypi.org/project/pytest-clang-tidy/)
[![Python](https://img.shields.io/pypi/pyversions/pytest-clang-tidy)](https://pypi.org/project/pytest-clang-tidy/)
[![License](https://img.shields.io/pypi/l/pytest-clang-tidy)](https://github.com/alexdej/pytest-clang-tidy/blob/main/LICENSE)

A pytest plugin that runs [clang-tidy](https://clang.llvm.org/extra/clang-tidy/) static
analysis on C/C++ source files. Each file is collected as a test item and
reported as a pass or failure in the normal pytest output.

Useful for Python projects with C/C++ source where you already run pytest
and want clang-tidy findings surfaced in the same test run.

## Installation

```
pip install pytest-clang-tidy
```

This pulls in clang-tidy automatically via the
[clang-tidy](https://pypi.org/project/clang-tidy/) PyPI package.

## Usage

The plugin does nothing unless explicitly enabled:

```
pytest --clang-tidy
```

This collects all `.c` and `.cpp` files and runs clang-tidy on each one.
Files with errors fail; clean files pass.

```
PASSED src/clean.c::CLANG_TIDY
FAILED src/buggy.c::CLANG_TIDY
  src/buggy.c:4:8: error: Dereference of null pointer (loaded from
  variable 'p') [clang-analyzer-core.NullDereference]
```

You can combine `--clang-tidy` with your normal test run — Python tests and
clang-tidy items appear together in the results.

## Configuration

All options go in `pyproject.toml`, `pytest.ini`, or `setup.cfg` under `[pytest]`.

### `clang_tidy_args`

Extra arguments forwarded to every clang-tidy invocation. This is the main
configuration surface — use it for `-checks`, `--warnings-as-errors`, and any
other clang-tidy flags.

By default, clang-tidy exits 0 even when it finds warnings. To make warnings
fail the test, add `--warnings-as-errors=*`. A good starting configuration:

```ini
[pytest]
clang_tidy_args =
    -checks=-*,clang-analyzer-*
    --warnings-as-errors=*
```

Without `--warnings-as-errors`, warnings from clang-tidy are still surfaced
as Python warnings in the pytest output (visible in the warnings summary).

### `clang_tidy_extensions`

File extensions to collect. Default: `.c .cpp`.

```ini
[pytest]
clang_tidy_extensions = .c .cpp .h
```

### `clang_tidy_compiler_args`

Extra compiler arguments passed after `--` in the clang-tidy invocation.
Useful for passing defines, include paths, or language standards.

```ini
[pytest]
clang_tidy_compiler_args = -std=c11 -DNDEBUG
```

### `compile_commands.json`

If a `compile_commands.json` file exists in your project root, clang-tidy
will use it automatically and the plugin will not append any compiler flags.
When no `compile_commands.json` is found, the plugin passes `--` with
`-isystem<python_include>` (the CPython headers directory) and any
`clang_tidy_compiler_args` so that clang-tidy can parse files that
`#include <Python.h>`.

## Markers

All clang-tidy items are marked with `clang_tidy`, so you can select or exclude
them with `-m`:

```
pytest --clang-tidy -m clang_tidy           # only clang-tidy
pytest --clang-tidy -m "unit or clang_tidy" # unit tests + clang-tidy
pytest --clang-tidy -m "not clang_tidy"     # everything except clang-tidy
```

## Caching

Results are cached based on file modification time, `clang_tidy_args`, and
`clang_tidy_compiler_args`. On subsequent runs, files that previously passed
are skipped. The cache is automatically invalidated when a file is modified
or arguments change. Caching relies on pytest's built-in cache provider
(the `.pytest_cache` directory). If the cache provider is disabled (for
example with `-p no:cacheprovider`), results will not be cached and all files
will be re-checked on each run.

To force a full re-check:

```
pytest --clang-tidy --cache-clear
```

## License

MIT
