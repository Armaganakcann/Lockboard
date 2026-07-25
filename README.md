# AIOS — Artificial Intelligence Operating System

> A minimal, extensible **reference runtime** for AI components.

[![CI](https://github.com/armaganakcan/aios/actions/workflows/ci.yml/badge.svg)](https://github.com/armaganakcan/aios/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status: alpha](https://img.shields.io/badge/status-alpha-orange.svg)](CHANGELOG.md)
[![Checked with mypy](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy-lang.org/)
[![Linted with Ruff](https://img.shields.io/badge/ruff-checked-purple.svg)](https://docs.astral.sh/ruff/)

---

## What is AIOS?

AIOS is **not** a model, a framework, an LLM, a chatbot, or an agent.

AIOS is an **Operating Layer / Runtime**: the shared execution environment in
which AI applications run and have their lifecycle managed. Its job is not to
build AI models — it is to *run the components* that make up AI systems, with a
predictable, well-tested lifecycle.

This release ships the **runtime core only**. Larger subsystems (event bus,
plugin manager, scheduler, workflow engine, registry, MCP integration,
multi-agent / distributed / cloud / edge runtimes) are intentionally left out
and documented as [extension points](docs/extension-points.md).

## Why AIOS?

- **Minimum Core.** If a feature can live outside the core, it stays outside.
  The runtime is small enough to read in one sitting and hard to accidentally
  bloat.
- **Predictable lifecycle.** `initialize → execute → shutdown`, with `shutdown`
  guaranteed to run and errors that never silently disappear.
- **Typed and strict.** Full type hints, `py.typed` shipped (PEP 561), passing
  `mypy --strict`.
- **Extensible by design.** Plugins, workflow engines, and event buses attach at
  documented seams — without modifying the core.
- **Professional from day one.** Versioned manifests, a clean exception
  hierarchy, library-safe logging, and a real test suite.

## Installation

Requires **Python 3.12+**.

```bash
pip install -e .
```

With development tooling (pytest, ruff, mypy):

```bash
pip install -e ".[dev]"
```

## Quick start

```bash
aios version
aios run examples/hello.yaml
```

Expected output:

```
Hello AIOS!
```

Increase log verbosity with `-v` / `-vv`:

```bash
aios run examples/hello.yaml -v
```

## Example component

```python
from aios import Component, ExecutionContext, ExecutionResult


class HelloComponent(Component):
    def execute(self, context: ExecutionContext) -> ExecutionResult:
        context.logger.info("running")
        return ExecutionResult.ok("Hello AIOS!")
```

`initialize()` and `shutdown()` are optional hooks — override them only when you
need setup or cleanup.

## Manifest example

A manifest is a small, **versioned** YAML file that tells the runtime which
component to run:

```yaml
# hello.yaml
version: 1
component:
  module: examples.hello_component
  class: HelloComponent
```

Run it:

```bash
aios run hello.yaml
```

## Runtime lifecycle

`Runtime.run()` executes exactly one deterministic flow:

```
 read manifest → validate → load component → build context
              → initialize() → execute() → shutdown()
```

Guarantees:

- **`shutdown()` always runs**, even if `initialize()` or `execute()` raise.
- A `shutdown()` failure **after** successful execution is surfaced as a
  `RuntimeExecutionError`, never silently swallowed.
- If the body already failed, a `shutdown()` failure is logged so it cannot
  mask the original error.
- `execute()` must return an `ExecutionResult`; anything else is an error.

## Project structure

```
AIOS/
├── pyproject.toml          # hatchling build, entry point, ruff/mypy/pytest config
├── README.md · LICENSE · CHANGELOG.md
├── CONTRIBUTING.md · CODE_OF_CONDUCT.md · SECURITY.md
├── .github/                # CI, issue/PR templates, dependabot, CODEOWNERS
├── docs/
│   └── extension-points.md
├── examples/
│   ├── hello.yaml
│   └── hello_component.py
├── tests/
└── src/aios/
    ├── __init__.py         # public API + __version__
    ├── py.typed            # PEP 561 typing marker
    ├── exceptions.py       # AIOSError hierarchy
    ├── logger.py           # library-safe logging
    ├── context.py          # ExecutionContext, ExecutionResult
    ├── component.py        # Component ABC (lifecycle contract)
    ├── manifest.py         # versioned schema + version dispatch
    ├── loader.py           # dynamic importlib loader
    ├── runtime.py          # orchestration with guaranteed shutdown
    └── cli/                # Click-based `aios` CLI
```

## Roadmap

Planned as **independent modules**, never welded to the core:

- [ ] Plugin manager (entry-point discovery)
- [ ] Component registry
- [ ] Event bus / observer hooks
- [ ] Scheduler
- [ ] Workflow engine
- [ ] Configuration management
- [ ] Metrics & tracing
- [ ] Async runtime
- [ ] Distributed / cloud / edge runtimes
- [ ] MCP integration & multi-agent runtime

See [docs/extension-points.md](docs/extension-points.md) for how each attaches
without touching the core.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for the
development setup, quality gates, and the Minimum Core principle, and follow our
[Code of Conduct](CODE_OF_CONDUCT.md).

Quality gates (also enforced by CI on Python 3.12 and 3.13):

```bash
ruff check .
mypy
pytest
```

## License

MIT — see [LICENSE](LICENSE).
