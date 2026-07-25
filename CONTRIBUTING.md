# Contributing to AIOS

Thanks for your interest in improving AIOS! This document explains how to set up
your environment, the quality bar we hold, and the one principle that shapes
every decision in this project.

## The Minimum Core principle

AIOS is a **runtime core**, deliberately kept small. Before proposing a change,
ask:

1. Is this strictly required for the runtime to run a component?
2. Could it live as a plugin or an external module instead?
3. If it can be added without modifying the runtime, why put it in the core?

**If it does not belong in the core, it should not go in the core.** Most new
capabilities belong in future plugins, not in `aios/`.

## Development setup

Requires **Python 3.12+**.

```bash
git clone https://github.com/armaganakcan/aios.git
cd aios
python -m pip install -e ".[dev]"
```

## Quality gates

Every change must pass all three checks locally before you open a pull request.
CI runs the same checks on Python 3.12 and 3.13.

```bash
ruff check .      # linting
mypy              # strict type checking
pytest            # tests
```

- **Type hints are mandatory** on all public functions and methods.
- **Docstrings are mandatory** on public modules, classes, and functions.
- Add or update **tests** for any behavior change, including edge cases.

## Public API stability

The following are considered the stable public API and should not change
without a clear, documented justification:

- `Component`
- `ExecutionContext`, `ExecutionResult`
- `Runtime.run()`
- `load_manifest()`, `load_component()`

Widening an input type (e.g. accepting `str` in addition to `Path`) is
acceptable because it is backward compatible. Narrowing or renaming is a
breaking change and must be called out.

## Commit and pull request guidelines

- Keep pull requests focused and small.
- Write clear commit messages in the imperative mood
  (e.g. "Fix shutdown error precedence").
- Fill in the pull request template, including the Minimum Core checkbox.
- Reference any related issue (e.g. `Closes #12`).

## Project layout

```
src/aios/      # the runtime core (small on purpose)
tests/         # pytest suite
examples/      # runnable examples
docs/          # architecture & extension-point notes
```

## Reporting bugs and requesting features

- Bugs: open a **Bug Report** issue with reproduction steps and versions.
- Features: open a **Feature Request** and state whether it belongs in the core
  or as a plugin.
- Security issues: **do not** open a public issue — see [SECURITY.md](SECURITY.md).

## Code of Conduct

By participating, you agree to abide by our
[Code of Conduct](CODE_OF_CONDUCT.md).
