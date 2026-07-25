# ADR-0002: Plugin API

## Title

A minimal, types-only Plugin contract

## Status

Accepted — implemented (`aios/plugin.py`).

## Context

Runtime Hooks (ADR-0001) let code observe the lifecycle, but a hook is a bare
object: it has no identity (name, version), no lifecycle (resource setup and
cleanup), and no packaging story. To ship reusable extensions — and to give a
future Plugin Manager something stable to build on — we need a **plugin
contract**.

The constraint is Minimum Core: the contract must not grow the runtime, must not
change the runtime, and must reuse the existing hook mechanism rather than
inventing a second extension mechanism.

## Decision

Define the plugin contract as **types only**, in a small module that the runtime
never imports.

- `Plugin` — an `ABC`. Only `metadata` is mandatory (an abstract property);
  `setup(context)`, `hooks()`, and `teardown()` are optional and default to
  no-ops. `hooks()` returns an empty tuple by default. A plugin is a
  lifecycle-managed unit that **produces** `RuntimeHook` objects.
- `PluginMetadata` — a frozen dataclass carrying identity only:
  `name`, `version`, `description = ""`, `api_version = "1"`.
- `PluginContext` — a frozen, read-only dataclass passed to `setup`:
  `logger`, `config`, `aios_version`.

### Why a `Plugin` class (ABC)

An ABC mirrors the existing `Component` contract (mandatory core method,
optional lifecycle hooks with no-op defaults), so the model is already familiar.
Making only `metadata` abstract forces identity while keeping trivial plugins
concise. A plugin reuses the hook system: it returns hooks, and the runtime
remains the only consumer of hooks.

### Why `PluginContext` is immutable

`setup` receives a read-only snapshot (a scoped logger, its configuration, the
host version) rather than a handle to runtime internals. Immutability keeps the
seam narrow, prevents plugins from mutating shared state, and is consistent with
`ExecutionContext`/`HookContext`.

### Why `PluginMetadata`

Identity is required by any manager to de-duplicate, order, report, and check
compatibility (`api_version`). Keeping it a separate frozen value object
(behaviour-free) makes the plugin's identity stable and comparable.

### Why the API is minimal

The contract is intentionally small. There is **no** `PluginCapabilities`
descriptor (a plugin contributes hooks in v1; declaring capabilities would be
speculative) and **no** control-plane types. This mirrors the ADR-0001 decision
to omit `HookResult`. Future contribution kinds can be added later as additive,
optional methods on `Plugin` without breaking the contract.

## Alternatives Considered

- **Capability / `PluginContext.register_*` API** — plugins push contributions
  (hooks, components, services) into a registration context. More flexible but
  turns the context into a growing, mutable, capability-laden surface (contract
  creep), higher to learn and maintain. The same power can be reached later
  additively, so this was rejected as premature (YAGNI).
- **No core contract (manager-owned / duck-typed)** — the core adds nothing and
  each manager invents its own interface. Maximally minimal for the core, but
  leaves no shared, stable contract, risking ecosystem fragmentation — exactly
  what "a contract the Plugin Manager builds on" must avoid. Rejected; the
  types-only contract (like `hooks.py`) is the right balance.

## Consequences

- The core gains three small types (`aios/plugin.py`); nothing in the runtime
  imports them, and no existing public API changed.
- Metrics, tracing, and logging ship as plugins that produce observational
  hooks (see the first-party plugins under `aios/plugins/`).
- Plugins may be stateful and hold resources (unlike stateless components); the
  Plugin Manager (ADR-0003) manages their coarse setup/teardown lifecycle.
- A plugin can be used without a manager: it is just an object whose
  `setup`/`hooks`/`teardown` can be driven directly.

## Related RFC

RFC-0002 — Plugin API Design Proposal.
