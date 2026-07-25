# ADR-0001: Runtime Hooks

## Title

Observational Runtime Hooks for the AIOS lifecycle

## Status

Accepted — implemented (`aios/hooks.py`, `aios/runtime.py`).

## Context

The runtime executes one deterministic flow:

```
manifest → validate → load → context → initialize() → execute() → shutdown()
```

Future subsystems (metrics, tracing, logging, telemetry, and later an event bus
or workflow observability) need to attach to points in this flow. Without a
seam, every such need would require editing `runtime.py`, growing the core and
coupling it to those subsystems — a direct violation of the Minimum Core
principle.

We needed the **smallest** primitive that lets code observe the lifecycle from
the outside, without adding control-flow power we do not yet need.

## Decision

Introduce a **purely observational** hook contract, injected into the runtime
by constructor and emitted at fixed lifecycle points.

- `LifecyclePhase` — an `enum` of the ten observable points
  (`RUN_START`, `COMPONENT_LOADED`, `BEFORE_INITIALIZE`, `AFTER_INITIALIZE`,
  `BEFORE_EXECUTE`, `AFTER_EXECUTE`, `ON_ERROR`, `BEFORE_SHUTDOWN`,
  `AFTER_SHUTDOWN`, `RUN_END`). No magic strings.
- `HookContext` — a frozen, read-only snapshot for one phase
  (`phase`, `run_id`, `component_name`, `metadata`, `execution_context`,
  `result`, `error`, `elapsed`).
- `RuntimeHook` — a `Protocol` with a **single** method,
  `on_lifecycle(context) -> None`. One method keeps the interface stable:
  adding a phase never changes it.
- `Runtime(hooks=...)` — hooks are injected via the constructor; `Runtime.run()`
  is unchanged. The runtime emits through a **private** `_emit`.

### Why the runtime did not change (behaviourally)

`Runtime.run()` keeps its signature and its guarantees. When no hooks are
registered, `_emit` returns immediately (no `run_id` generated, no `HookContext`
built), so the cost is negligible and behaviour is byte-for-byte identical. The
existing shutdown guarantee and error precedence are preserved; `RUN_END`
always fires.

### Why hooks are observational only

Hooks cannot alter the context, the result, or the flow. There is deliberately
**no** `HookResult`. All primary use cases (metrics, tracing, logging) are
observational, and the runtime measures timing itself and passes it in
`HookContext`, so observers need no cross-phase state to time a call. Keeping
hooks read-only preserves `ExecutionContext`/`ExecutionResult` immutability and
the runtime's guarantees.

### Error isolation

A hook that raises is caught and logged by the runtime; it never stops the run,
affects the component, or blocks other hooks. `KeyboardInterrupt`/`SystemExit`
still propagate.

## Alternatives Considered

- **Middleware / onion pipeline** (`(context, next) -> result`). More powerful —
  wrapping, short-circuit, result mutation — but adds control-flow power we do
  not need, a higher learning cost, and risk to the immutability/guarantee
  story. It can be added later as a separate opt-in layer without breaking
  observers, so it was deferred, not foreclosed.
- **Event emitter / signal bus** (pub-sub with named events). This *is* the
  event bus, which the roadmap lists as a separate future module. Embedding it
  in the core to enable extension contradicts Minimum Core, and string-keyed
  events with loosely typed payloads weaken type safety. Rejected for the core;
  an event bus can instead be built **on top** of hooks as a single hook that
  re-broadcasts events.

## Consequences

- The core gains three small, dependency-free types; the runtime gains only
  private `_emit` calls.
- Metrics, tracing, logging, and telemetry become observers, not core code.
- An event bus, a plugin manager, and workflow observability can all be built on
  this primitive without touching the runtime.
- Hooks are single-threaded and synchronous, matching the runtime; `run_id` is
  carried from day one so a future async/concurrent runtime can correlate
  phases.
- Reordering or removing a `LifecyclePhase` is a breaking change; the enum is
  treated as a public contract and only extended additively.

## Related RFC

RFC-0001 — Runtime Hooks Design Proposal.
