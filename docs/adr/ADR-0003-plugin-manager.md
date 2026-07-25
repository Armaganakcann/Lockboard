# ADR-0003: Plugin Manager

## Title

A single-class Plugin Manager outside the runtime core

## Status

Accepted — implemented (`aios/plugin_manager.py`).

## Context

The Plugin API (ADR-0002) defines what a plugin *is*, but something must
discover plugins, instantiate them, validate compatibility, set them up,
aggregate their hooks into a `Runtime(hooks=...)`, and tear them down. This
orchestration is neither the runtime's job (the runtime must not learn about
plugins) nor a plugin's job. It belongs to a separate **Plugin Manager** layer.

The dependency direction must stay manager → runtime, and the runtime, the hook
system, and the Plugin API must not change.

## Decision

Implement a **single public type**, `PluginManager`, in a module outside the
runtime core.

- Constructor:
  `PluginManager(plugins=(), discover_entry_points=False,
  entry_point_group="aios.plugins", config=None, strict=False)`.
- Lifecycle: `discover → instantiate → validate(api_version) → setup(context)
  → collect hooks → Runtime(hooks=...) → teardown`.
- `start() -> Runtime`, `close()`, and context-manager support
  (`with PluginManager(...) as runtime:`). `start()` is idempotent.
- Determinism: manual registration order is preserved; entry-point plugins are
  sorted by `metadata.name`; duplicates are removed by `metadata.name`
  (manual wins over entry-point).
- Errors surface as `PluginError` (a subclass of `AIOSError`).

### Why no Loader, Registry, or Pipeline

The manager's work is linear and one-shot. A separate `PluginLoader` and
`PluginRegistry` (or a staged pipeline) would add public types, learning cost,
and maintenance for no present benefit — the speculative abstraction Minimum
Core warns against. Discovery and aggregation are private helpers inside
`PluginManager`. If a real need arises (e.g. pluggable discovery), it can be
factored in later **without changing the public surface**.

### Why `strict=False` is the default

Resilience is the safer default for an observability layer: one broken plugin
must not take down a run. By default, an instantiate/validate/setup failure
disables just that plugin; a `hooks()` failure yields zero hooks; a teardown
failure is logged and the remaining teardowns still run. `strict=True` opts into
fail-fast, raising `PluginError` on the first activation error (and, on abort,
tearing down already-set-up plugins). This mirrors the hook and runtime error
policies: isolate by default, never mask.

### Why entry points are optional (default off)

Auto-loading installed entry points executes third-party code implicitly.
Making discovery explicit (`discover_entry_points=True`) keeps manual
registration the baseline, avoids surprising code execution, and matches AIOS's
preference for explicitness. Entry-point iteration order is not stable, so
discovered plugins are always sorted by name for reproducibility. The
first-party plugins (`logging`, `metrics`, `tracing`) are registered under the
`aios.plugins` group and are discovered only when discovery is enabled.

## Alternatives Considered

- **Registry-based** (`PluginLoader` + `PluginRegistry` + `PluginManager`) —
  cleaner SRP but three public types and more surface than a small, linear
  manager needs. Rejected as over-engineering.
- **Pipeline / stage-based** — explicit composable stages, but pipeline
  machinery is itself overhead for a linear, one-shot bootstrap. Rejected
  (YAGNI).
- **Entry points on by default** — more convenient but runs third-party code
  without consent; rejected in favour of explicit opt-in.
- **Priority system for ordering** — rejected; deterministic order comes from
  registration order plus name-sorting, consistent with the hooks decision to
  avoid a priority mechanism.

## Consequences

- The manager is a separate module; the runtime never imports it and is
  unchanged, as are `Component`, the hook system, and the Plugin API.
- Plugins are set up once, before runs, and torn down once, after runs (LIFO);
  the per-run hook lifecycle (ADR-0001) is the finer, nested scope.
- Failed-setup plugins are not torn down, so `setup` must be atomic and clean up
  its own partial state on failure.
- Metrics, tracing, and logging plugins are assembled by the manager into one
  configured runtime; workflow engines and schedulers can consume that runtime
  from above without special support.

## Related RFC

RFC-0003 — Plugin Manager Architecture.
