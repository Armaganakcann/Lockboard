"""Runtime orchestration: read → validate → load → run → shutdown.

The :class:`Runtime` is intentionally minimal. Cross-cutting concerns (event
bus, scheduling, plugin discovery, workflow engine) are explicit future
extension points and are **not** embedded here.

The runtime optionally accepts observational lifecycle hooks (RFC-0001). Hooks
never influence execution: they cannot alter the context, the result, or the
flow, and a failing hook is isolated and logged.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

from aios.component import Component
from aios.context import ExecutionContext, ExecutionResult
from aios.exceptions import AIOSError, RuntimeExecutionError
from aios.hooks import HookContext, LifecyclePhase, RuntimeHook
from aios.loader import load_component
from aios.logger import get_logger
from aios.manifest import Manifest, load_manifest

_COMPONENT_LOGGER_PREFIX = "component"


class Runtime:
    """Executes a single component described by a manifest.

    Args:
        hooks: Optional observational lifecycle hooks. When empty (the default),
            the runtime behaves exactly as before and emits nothing.
    """

    def __init__(self, hooks: Sequence[RuntimeHook] = ()) -> None:
        """Create a runtime with its own scoped logger and optional hooks."""
        self._logger = get_logger("runtime")
        self._hooks: tuple[RuntimeHook, ...] = tuple(hooks)

    def run(self, manifest_path: str | Path) -> ExecutionResult:
        """Run the component referenced by the manifest at ``manifest_path``.

        The lifecycle is guaranteed: ``shutdown`` always runs, even when
        ``initialize`` or ``execute`` raise.

        Args:
            manifest_path: Path to a YAML manifest file. A plain ``str`` is
                accepted and coerced to :class:`~pathlib.Path`.

        Returns:
            The :class:`ExecutionResult` produced by the component.

        Raises:
            ManifestError: If the manifest is missing or invalid.
            ComponentLoadError: If the component cannot be loaded.
            RuntimeExecutionError: If execution fails unexpectedly, or if a
                ``shutdown`` failure occurs after otherwise-successful execution.
        """
        manifest = load_manifest(manifest_path)
        component = load_component(manifest.component)
        context = self._build_context(manifest)
        run_id = uuid4().hex if self._hooks else ""
        run_started = time.monotonic()

        self._logger.info("Starting component '%s'", context.component_name)
        self._emit(LifecyclePhase.RUN_START, context, run_id=run_id)
        self._emit(LifecyclePhase.COMPONENT_LOADED, context, run_id=run_id)

        body_error: Exception | None = None
        try:
            self._emit(LifecyclePhase.BEFORE_INITIALIZE, context, run_id=run_id)
            component.initialize(context)
            self._emit(LifecyclePhase.AFTER_INITIALIZE, context, run_id=run_id)

            self._emit(LifecyclePhase.BEFORE_EXECUTE, context, run_id=run_id)
            execute_started = time.monotonic()
            result = self._validate_result(component, component.execute(context))
            execute_elapsed = time.monotonic() - execute_started
            self._emit(
                LifecyclePhase.AFTER_EXECUTE,
                context,
                run_id=run_id,
                result=result,
                elapsed=execute_elapsed,
            )

            self._logger.info(
                "Component '%s' finished (success=%s)",
                context.component_name,
                result.success,
            )
            return result
        except AIOSError as exc:
            body_error = exc
            self._emit(LifecyclePhase.ON_ERROR, context, run_id=run_id, error=exc)
            raise
        except Exception as exc:  # broad on purpose: normalised into an AIOS error type
            wrapped = RuntimeExecutionError(
                f"Component '{context.component_name}' raised an unexpected error: {exc}"
            )
            body_error = wrapped
            self._emit(LifecyclePhase.ON_ERROR, context, run_id=run_id, error=wrapped)
            raise wrapped from exc
        finally:
            self._emit(LifecyclePhase.BEFORE_SHUTDOWN, context, run_id=run_id)
            try:
                self._run_shutdown(component, context, body_error)
            finally:
                self._emit(LifecyclePhase.AFTER_SHUTDOWN, context, run_id=run_id)
                self._emit(
                    LifecyclePhase.RUN_END,
                    context,
                    run_id=run_id,
                    elapsed=time.monotonic() - run_started,
                )

    def _build_context(self, manifest: Manifest) -> ExecutionContext:
        """Assemble the immutable context for the manifest's component."""
        spec = manifest.component
        return ExecutionContext(
            component_name=spec.class_name,
            logger=get_logger(f"{_COMPONENT_LOGGER_PREFIX}.{spec.class_name}"),
            config={},
            metadata={"module": spec.module, "class": spec.class_name},
        )

    def _validate_result(self, component: Component, result: object) -> ExecutionResult:
        """Ensure ``execute`` honoured the return contract."""
        if not isinstance(result, ExecutionResult):
            raise RuntimeExecutionError(
                f"{type(component).__name__}.execute must return an ExecutionResult, "
                f"got {type(result).__name__}."
            )
        return result

    def _run_shutdown(
        self,
        component: Component,
        context: ExecutionContext,
        body_error: Exception | None,
    ) -> None:
        """Invoke ``shutdown`` with correct error precedence.

        If the body already failed (``body_error`` is set), a shutdown failure
        is logged so it never masks the original error. If the body succeeded,
        a shutdown failure is surfaced as a :class:`RuntimeExecutionError`
        rather than being silently swallowed.
        """
        try:
            component.shutdown(context)
        except Exception as exc:  # broad on purpose: precedence handled below
            if body_error is not None:
                self._logger.error(
                    "shutdown() failed for component '%s' while handling a prior error: %s",
                    context.component_name,
                    exc,
                )
            else:
                raise RuntimeExecutionError(
                    f"shutdown() failed for component '{context.component_name}': {exc}"
                ) from exc

    def _emit(
        self,
        phase: LifecyclePhase,
        context: ExecutionContext,
        *,
        run_id: str,
        result: ExecutionResult | None = None,
        error: BaseException | None = None,
        elapsed: float | None = None,
    ) -> None:
        """Notify every hook of a lifecycle phase.

        This method never raises: a hook that fails is isolated and logged so it
        cannot stop the runtime, affect the component, or block other hooks.
        When no hooks are registered it returns immediately, so the cost is
        negligible for the common case.
        """
        if not self._hooks:
            return

        hook_context = HookContext(
            phase=phase,
            run_id=run_id,
            component_name=context.component_name,
            metadata=context.metadata,
            execution_context=context,
            result=result,
            error=error,
            elapsed=elapsed,
        )
        for hook in self._hooks:
            try:
                hook.on_lifecycle(hook_context)
            except Exception as exc:  # hook errors are isolated and only logged
                self._logger.error(
                    "Hook %s failed during %s: %s",
                    type(hook).__name__,
                    phase.name,
                    exc,
                )
