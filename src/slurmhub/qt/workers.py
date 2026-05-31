"""Qt worker primitives.

The UI thread must never call ``SSHClient.execute``/``stream_command`` or
``Repository.*`` directly (they block on network / disk I/O). :class:`FetchTask`
wraps any plain data-layer callable in a ``QRunnable`` so it runs on the global
``QThreadPool``; the result (or exception) is delivered back to the main thread
through queued signal connections. This is the Qt analogue of Textual's
``run_worker(thread=True)`` + ``on_worker_state_changed``.
"""

from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QRunnable, Signal, Slot, QThreadPool


class WorkerSignals(QObject):
    """Signal carrier for a :class:`FetchTask` (a ``QRunnable`` is not a ``QObject``)."""

    finished = Signal(object)
    failed = Signal(Exception)


class FetchTask(QRunnable):
    """Run ``fn(*args, **kwargs)`` on a worker thread and emit the result."""

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:  # noqa: D401 — QRunnable entry point
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 — surfaced to the UI via signal
            self.signals.failed.emit(exc)
        else:
            self.signals.finished.emit(result)


def run_async(
    fn: Callable[[], Any],
    on_finished: Callable[[Any], None],
    on_failed: Optional[Callable[[Exception], None]] = None,
) -> FetchTask:
    """Run ``fn`` on the global pool and deliver the result to ``on_finished``.

    IMPORTANT: ``on_finished`` / ``on_failed`` must be **bound methods of a
    QObject** (e.g. ``self._on_loaded``), not bare lambdas — a functor with no
    receiver QObject is not queued onto the main thread for a cross-thread emit.
    """
    task = FetchTask(fn)
    task.signals.finished.connect(on_finished)
    if on_failed is not None:
        task.signals.failed.connect(on_failed)
    QThreadPool.globalInstance().start(task)
    return task
