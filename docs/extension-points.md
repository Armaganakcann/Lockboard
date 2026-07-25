# Extension Points

AIOS keeps its core minimal on purpose. This document records the seams where
future subsystems attach **without** modifying the runtime core. Each of these
is deliberately *not* implemented yet.

## Design rule

Before anything is added to the core, it must pass three questions:

1. Is it strictly required for the runtime to run a single component?
2. Can it later be added as an independent module instead?
3. Would embedding it now create long-term coupling?

If a feature can live outside the core, it stays outside the core.

## Why there is no `registry.py` in the core

A component registry is **not** required to load and run a single component
from a manifest — the loader resolves the class directly via `importlib`.
A registry only becomes meaningful once plugin discovery exists. Its natural
home is `importlib.metadata` entry points, delivered as a separate module.
Adding it to the core now would violate the minimum-core rule, so it is
documented here instead.

## The seams

| Future subsystem      | Attachment point                                              |
| --------------------- | ------------------------------------------------------------- |
| Plugin manager        | `loader.py` + packaging entry points (`importlib.metadata`)   |
| Component registry     | New module built on the plugin discovery seam                 |
| Configuration mgmt    | `ExecutionContext.config` (already a read-only mapping)        |
| Metrics / tracing     | `ExecutionContext.metadata` + logger; wrap `Runtime.run`      |
| Event bus / observers | `Runtime` lifecycle hooks (before/after initialize/execute)   |
| Scheduler             | A caller that drives `Runtime.run` on a schedule              |
| Workflow engine       | Composes multiple manifests/components above the runtime      |
| Manifest evolution    | `manifest.py` version dispatch table (`_MANIFEST_MODELS`)     |
| Async runtime         | An `AsyncComponent` contract + an async runner alongside      |
| Distributed runtime   | Stateless components + immutable `ExecutionContext`           |

## Manifest versioning

`parse_manifest` dispatches on the `version` field. Adding a `ManifestV2`
means: define the model, register it in `_MANIFEST_MODELS`, and update the
`Manifest` union. Existing v1 manifests keep working untouched.
