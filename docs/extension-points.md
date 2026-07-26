# Extension Points

AIOS keeps its core minimal on purpose. This document records the seams where
subsystems attach **without** modifying the runtime core. Some of these are now
implemented as separate modules built on the hook and plugin systems; the rest
are deliberately deferred. See [adr/](adr/) for the decisions behind the
implemented seams.

## Design rule

Before anything is added to the core, it must pass three questions:

1. Is it strictly required for the runtime to run a single component?
2. Can it later be added as an independent module instead?
3. Would embedding it now create long-term coupling?

If a feature can live outside the core, it stays outside the core.

## Why there is no `registry.py` in the core

A component registry is **not** required to load and run a single component
from a manifest — the loader resolves the class directly via `importlib`.
Plugin discovery now exists (Python entry points, via the plugin manager), but a
component registry is still deferred: it is not needed to run the runtime and
would belong in a separate module. Adding it to the core now would violate the
minimum-core rule, so it is documented here instead.

## The seams

| Subsystem                    | Status      | How it attaches                                                                 |
| ---------------------------- | ----------- | ------------------------------------------------------------------------------- |
| Runtime hooks                | Implemented | `RuntimeHook` + `LifecyclePhase` + `HookContext`, injected via `Runtime(hooks=...)` |
| Plugin API                   | Implemented | `Plugin` / `PluginMetadata` / `PluginContext` in `aios.plugin` (types only)     |
| Plugin manager               | Implemented | `aios.plugin_manager.PluginManager` — manual + entry-point discovery (`aios.plugins`) |
| Logging / metrics / tracing  | Implemented | First-party plugins in `aios.plugins` that contribute observational hooks       |
| Manifest evolution           | Available   | `manifest.py` version dispatch table (`_MANIFEST_MODELS`)                       |
| Configuration mgmt           | Planned     | `ExecutionContext.config` / `PluginContext.config` (already read-only mappings) |
| Event bus                    | Planned     | A single plugin/hook that re-broadcasts lifecycle events to subscribers          |
| Component registry           | Planned     | A separate module built on the entry-point discovery seam                       |
| Scheduler                    | Planned     | A caller that drives `Runtime.run` on a schedule                                |
| Workflow engine              | Planned     | Composes multiple runs above the runtime                                        |
| Async runtime                | Planned     | An `AsyncComponent` contract + an async runner alongside                        |
| Distributed runtime          | Planned     | Stateless components + immutable `ExecutionContext`                             |

## Manifest versioning

`parse_manifest` dispatches on the `version` field. Adding a `ManifestV2`
means: define the model, register it in `_MANIFEST_MODELS`, and update the
`Manifest` union. Existing v1 manifests keep working untouched.
