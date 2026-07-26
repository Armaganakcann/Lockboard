# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(with [PEP 440](https://peps.python.org/pep-0440/) pre-release identifiers for
Python packaging).

## [Unreleased]

## [0.3.0a1] — 2026-07-25

First public **alpha**. Released under the git tag `v0.3.0-alpha`
(PEP 440 canonical version: `0.3.0a1`).

This release ships the runtime core plus an observational hook system, a minimal
plugin API, a plugin manager, and three first-party plugins. Larger subsystems
(event bus, scheduler, workflow engine, registry, ...) are intentionally left
out and documented as extension points.

### Added

**Runtime core**

- Guaranteed lifecycle:
  `manifest → validate → load → context → initialize → execute → shutdown`.
- `Component` abstract base class with an optional `initialize`/`shutdown` and a
  mandatory `execute`.
- Immutable `ExecutionContext` and typed `ExecutionResult` value objects.
- **Versioned YAML manifests** (`version: 1`) with forward-compatible version
  dispatch (`parse_manifest`, `load_manifest`).
- `importlib`-based dynamic component loader (no hard-coded class names).
- Click-based CLI: `aios version` and `aios run <manifest>`.
- Library-safe logging: the core never configures the root logger
  (`NullHandler`); the CLI configures output via `configure_logging`.
- `AIOSError` exception hierarchy (`ManifestError`, `ComponentLoadError`,
  `RuntimeExecutionError`, `ConfigurationError`).
- Type information shipped to consumers via a `py.typed` marker (PEP 561).

**Runtime hooks (observational)**

- `LifecyclePhase` enum, immutable `HookContext`, and single-method
  `RuntimeHook` protocol.
- `Runtime(hooks=...)` constructor injection; `Runtime.run()` unchanged. Hooks
  cannot alter the flow, context, or result; a failing hook is isolated and
  logged. No cost when no hooks are registered.

**Plugin API (contract, types only)**

- `Plugin` ABC (mandatory `metadata`; optional `setup`/`hooks`/`teardown`),
  frozen `PluginMetadata`, and read-only `PluginContext`.

**Plugin manager**

- `PluginManager` orchestrates discovery → instantiate → validate(api_version)
  → setup → collect hooks → `Runtime(hooks=...)` → teardown, with manual
  registration and optional (off-by-default) Python entry-point discovery,
  deterministic ordering, de-duplication, and a `strict` error policy.

**First-party plugins**

- `LoggingPlugin`, `MetricsPlugin`, and `TracingPlugin`, registered under the
  `aios.plugins` entry-point group.

**Project**

- Test suite (pytest), linting (Ruff), strict type checking (mypy), CI on
  Python 3.12/3.13, and architecture decision records under `docs/adr/`.

### Behavior notes

These describe the runtime's guaranteed behavior for anyone building on top of
it; there is no prior public release to compare against.

- `shutdown()` **always runs**, even when `initialize()` or `execute()` raise.
- A `shutdown()` failure that occurs **after** otherwise-successful execution is
  surfaced as a `RuntimeExecutionError` rather than being silently swallowed.
  If the body already failed, a `shutdown()` failure is logged so it never
  masks the original error.
- `Runtime.run()` and `load_manifest()` accept both `str` and
  `pathlib.Path` inputs.
- A component whose `execute()` does not return an `ExecutionResult` raises a
  `RuntimeExecutionError`.

[Unreleased]: https://github.com/Armaganakcann/AIOS/compare/v0.3.0-alpha...HEAD
[0.3.0a1]: https://github.com/Armaganakcann/AIOS/releases/tag/v0.3.0-alpha
