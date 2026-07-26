# AIOS — Artificial Intelligence Operating System

> A small, strictly-typed runtime for AI components — built as a reproducible substrate for AI runtime and context-engineering research.

[![CI](https://github.com/Armaganakcann/AIOS/actions/workflows/ci.yml/badge.svg)](https://github.com/Armaganakcann/AIOS/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status: alpha](https://img.shields.io/badge/status-alpha-orange.svg)](CHANGELOG.md)
[![Checked with mypy](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy-lang.org/)
[![Linted with Ruff](https://img.shields.io/badge/ruff-checked-purple.svg)](https://docs.astral.sh/ruff/)

---

## What is AIOS?

AIOS is a small, strictly-typed Python **runtime** that executes AI *components* —
units of work declared in a manifest and run through an explicit
`initialize → execute → shutdown` lifecycle. It is **not** a model, an agent
framework, or an LLM library, and it does not call any model itself.

Its purpose is to be a **research substrate**: a deliberately minimal,
reproducible base for studying execution and context-management mechanisms in
AI systems. It is early and intentionally narrow — today it runs single
components with guaranteed lifecycle semantics, observational lifecycle hooks,
and a small plugin system. The core is kept stable so experimental mechanisms
can be attached at defined seams rather than by forking it.

On top of the runtime core, AIOS ships an **observational hook system**, a
minimal **plugin API**, a **plugin manager**, and three first-party plugins
(`logging`, `metrics`, `tracing`). Larger subsystems (event bus, scheduler,
workflow engine, registry, MCP integration, multi-agent / distributed / cloud /
edge runtimes) are intentionally left out and documented as
[extension points](docs/extension-points.md).

## Project goals

- Serve as a **reproducible substrate** for AI runtime research: deterministic,
  strictly-typed, and small enough to read in full.
- Provide **stable seams** (lifecycle hooks, plugins) so new execution or
  context-management mechanisms can be added and compared without forking the
  core.
- Keep the runtime **observable** — every lifecycle step is inspectable — so
  experiments can be measured rather than guessed.
- Prefer **correctness and clarity over features**: guaranteed lifecycle
  semantics, explicit error handling, and a minimal, tested core.

## Non-goals

- Not a production runtime, and not a competitor to Ray, Temporal, or Dapr.
- Not an agent framework or orchestration DSL — no reasoning graphs or
  multi-agent conversation patterns (see LangGraph, CrewAI, or the OpenAI
  Agents SDK for those).
- No built-in model, prompt, tool-calling, memory, or RAG abstractions.
- Not tied to any model vendor.
- No distributed, cloud, or GUI layer.

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

## Observability hooks

The runtime accepts optional, **purely observational** lifecycle hooks. Hooks
never change the flow, the context, or the result; a failing hook is isolated
and logged. With no hooks registered, the runtime behaves and performs exactly
as before.

```python
from aios import Runtime, HookContext, LifecyclePhase


class TimingHook:
    def on_lifecycle(self, context: HookContext) -> None:
        if context.phase is LifecyclePhase.RUN_END:
            print(f"run {context.run_id} took {context.elapsed:.3f}s")


Runtime(hooks=[TimingHook()]).run("examples/hello.yaml")
```

See [ADR-0001](docs/adr/ADR-0001-runtime-hooks.md) for the design rationale.

## Plugins

A **plugin** is a lifecycle-managed unit that contributes hooks. The
`PluginManager` discovers plugins (manual registration and, optionally, Python
entry points), sets them up, aggregates their hooks into a `Runtime`, and tears
them down.

```python
from aios.plugin_manager import PluginManager
from aios.plugins import LoggingPlugin, MetricsPlugin

metrics = MetricsPlugin()
with PluginManager(plugins=[LoggingPlugin(), metrics]) as runtime:
    runtime.run("examples/hello.yaml")

print(metrics.total_runs, metrics.average_elapsed)
```

Entry-point discovery is **off by default**; enable it with
`PluginManager(discover_entry_points=True)`. The first-party plugins are
registered under the `aios.plugins` group: `logging`, `metrics`, `tracing`.

See [ADR-0002](docs/adr/ADR-0002-plugin-api.md) (plugin API) and
[ADR-0003](docs/adr/ADR-0003-plugin-manager.md) (plugin manager).

## Project structure

```
AIOS/
├── pyproject.toml          # hatchling build, entry point, ruff/mypy/pytest config
├── README.md · LICENSE · CHANGELOG.md
├── CONTRIBUTING.md · CODE_OF_CONDUCT.md · SECURITY.md
├── .github/                # CI, issue/PR templates, dependabot, CODEOWNERS
├── docs/
│   ├── extension-points.md
│   └── adr/                # architecture decision records (ADR-0001..0003)
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
    ├── hooks.py            # observational RuntimeHook contract
    ├── runtime.py          # orchestration with guaranteed shutdown
    ├── plugin.py           # Plugin API contract (types only)
    ├── plugin_manager.py   # PluginManager (separate layer)
    ├── cli/                # Click-based `aios` CLI
    └── plugins/            # first-party plugins: logging, metrics, tracing
```

## Roadmap

Shipped:

- [x] Observational runtime hooks
- [x] Plugin API (contract) and plugin manager (with entry-point discovery)
- [x] First-party plugins: logging, metrics, tracing

Planned as **independent modules**, never welded to the core:

- [ ] Component registry
- [ ] Event bus
- [ ] Scheduler
- [ ] Workflow engine
- [ ] Configuration management
- [ ] Async runtime
- [ ] Distributed / cloud / edge runtimes
- [ ] MCP integration & multi-agent runtime

See [docs/extension-points.md](docs/extension-points.md) for how each attaches
without touching the core, and [docs/adr/](docs/adr/) for the architecture
decision records behind the hook and plugin systems.

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
