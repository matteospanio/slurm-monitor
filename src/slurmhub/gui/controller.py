"""Application controller and per-profile session state for the Qt GUI.

This module owns the data side of the GUI: one :class:`ProfileSession` per
configured cluster, the periodic-refresh scheduling, and the worker dispatch
that keeps blocking SSH/DB calls off the UI thread. Views connect to the
controller's signals and read the (plain, detached) dataclasses it exposes.

The fetch orchestration (:func:`fetch_profile_data`), the per-profile state
container (:class:`ProfileSession`), the :class:`FetchResult` shape, and the
filter/sort logic (:func:`get_filtered_jobs`) are lifted from the Textual
``slurmhub.tui.app`` module so behaviour matches the proven TUI exactly.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThreadPool, QTimer, Signal

from slurmhub.config import AppConfig, ConfigLoader, ProfileConfig
from slurmhub.db import Database, Repository
from slurmhub.core.snapshot_cache import CachedSnapshot, SnapshotCache
from slurmhub.db.models import utcnow
from slurmhub.core.job_aggregator import (
    JobAggregator,
    filter_jobs_by_state,
    merge_jobs,
    sort_jobs_by_time,
)
from slurmhub.core.log_path_resolver import LogPathResolver
from slurmhub.core.queue_stats import (
    ClusterQueueStats,
    compute_queue_ranks,
    fetch_cluster_queue_stats,
    fetch_pending_details,
)
from slurmhub.gui.workers import FetchTask
from slurmhub.slurm.sacct import fetch_sacct_jobs
from slurmhub.slurm.sinfo import (
    ClusterCapacity,
    NodeStats,
    PartitionStats,
    fetch_sinfo,
)
from slurmhub.slurm.squeue import SlurmJob, fetch_squeue_jobs
from slurmhub.slurm.ssh import (
    DemoSSHClient,
    SSHAuthenticationError,
    SSHClient,
    SSHConnectionError,
    SSHTimeoutError,
)

SINFO_REFRESH_SECONDS = 60.0
QUEUE_STATS_REFRESH_SECONDS = 30.0

# Terminal job states that trigger a completion notification.
TERMINAL_STATES = {
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "TIMEOUT",
    "OUT_OF_MEMORY",
    "NODE_FAIL",
}


@dataclass
class FetchResult:
    """Result of a background job fetch (lifted from ``slurmhub.tui.app``)."""

    profile_name: str
    jobs: list[SlurmJob] = field(default_factory=list)
    queue_stats: Optional[ClusterQueueStats] = None
    cluster_capacity: Optional[ClusterCapacity] = None
    partitions: list[PartitionStats] = field(default_factory=list)
    nodes: list[NodeStats] = field(default_factory=list)
    sinfo_fetched: bool = False
    error: Optional[Exception] = None
    partial_errors: dict[str, str] = field(default_factory=dict)


class ProfileSession:
    """Per-cluster state container (lifted from ``slurmhub.tui.app.ProfileTab``)."""

    def __init__(self, profile: ProfileConfig, demo: bool = False) -> None:
        self.profile = profile
        self.ssh_client: SSHClient = (
            DemoSSHClient(profile.ssh) if demo else SSHClient(profile.ssh)
        )
        self.aggregator = JobAggregator(self.ssh_client, timeout=profile.ssh_timeout)
        self.path_resolver = LogPathResolver(profile.log)

        self.jobs: list[SlurmJob] = []
        self.queue_stats: Optional[ClusterQueueStats] = None
        self.cluster_capacity: Optional[ClusterCapacity] = None
        self.partitions: list[PartitionStats] = []
        self.nodes: list[NodeStats] = []

        # Connection / refresh state surfaced to the header strip.
        self.refresh_in_progress = False
        self.is_loading = False
        self.error_message: Optional[str] = None
        self.partial_errors: dict[str, str] = {}
        self.last_updated: Optional[str] = None
        # True while showing last-known cached data (no live fetch has yet
        # succeeded this session). State-changing actions stay disabled.
        self.is_cached = False

        # Internal fetch caches / cadences.
        self._sacct_cache: list[SlurmJob] = []
        self._sacct_last_fetch: float = 0.0
        self._queue_stats_last_fetch: float = 0.0
        self._sinfo_last_fetch: float = 0.0

        # Auth handling.
        self._auth_attempts: int = 0
        self.util_capture_in_progress = False

        # Serialize one-shot actions with refresh/utilization work for this
        # profile so the shared SSH session is never used concurrently.
        self.action_in_progress = False
        self.action_verb = ""
        self.action_job_id = ""
        self.pending_refresh = False
        self.pending_actions: list[tuple[str, str, str]] = []

        # Job-state tracking for completion notifications.
        self._prev_states: dict[str, str] = {}
        self._states_seen: bool = False

        # Per-profile view state (each profile remembers its own view).
        self.state_filter: str = "ALL"
        self.name_filter: str = ""
        self.sort_mode: str = "id"  # id, time, state, name
        self.queue_scope: str = "me"  # me, all

    def close(self) -> None:
        self.ssh_client.close()


def get_filtered_jobs(session: ProfileSession) -> list[SlurmJob]:
    """Apply the session's state filter, name filter, and sort (lifted from app)."""
    filtered = session.jobs

    if session.state_filter != "ALL":
        filtered = filter_jobs_by_state(filtered, [session.state_filter])

    if session.name_filter:
        query = session.name_filter.lower()
        filtered = [j for j in filtered if query in j.name.lower() or query in j.job_id]

    if session.sort_mode == "time":
        filtered = sort_jobs_by_time(filtered)
    elif session.sort_mode == "name":
        filtered = sorted(filtered, key=lambda j: j.name.lower())
    elif session.sort_mode == "state":
        filtered = sorted(filtered, key=lambda j: j.state)
    # "id" is the default (already sorted by merge_jobs)

    return filtered


def fetch_profile_data(
    session: ProfileSession,
    profile_name: str,
    database: Optional[Database],
    repository: Optional[Repository],
) -> FetchResult:
    """Fetch all data for one profile on a worker thread.

    Mirrors ``slurmhub.tui.app.SlurmhubApp._fetch_jobs``: squeue every cycle, sacct
    on its slower cadence, queue stats (~30 s), pending enrichment, and sinfo
    (~60 s). SSH errors are returned in ``FetchResult.error``; auxiliary
    failures land in ``partial_errors``. Any other exception propagates to the
    worker's ``failed`` signal.
    """
    profile = session.profile
    timeout = profile.ssh_timeout
    try:
        include_all = session.queue_scope == "all"
        active_jobs = fetch_squeue_jobs(
            session.ssh_client,
            timeout=timeout,
            include_all=include_all,
        )

        now = time.time()
        if now - session._sacct_last_fetch > profile.sacct_refresh_interval:
            sacct_jobs = fetch_sacct_jobs(session.ssh_client, timeout=timeout)
            session._sacct_cache = sacct_jobs
            session._sacct_last_fetch = now
        else:
            sacct_jobs = session._sacct_cache

        if include_all:
            # Cluster scope is an active-queue display mode; keep history rows
            # sourced from the current user's jobs only.
            historical_jobs = []
        else:
            historical_jobs = sacct_jobs

        merged = merge_jobs(active_jobs, historical_jobs)

        partial_errors: dict[str, str] = {}

        queue_stats = session.queue_stats
        try:
            if now - session._queue_stats_last_fetch > QUEUE_STATS_REFRESH_SECONDS:
                queue_stats = fetch_cluster_queue_stats(
                    session.ssh_client, timeout=timeout
                )
                session._queue_stats_last_fetch = now
        except Exception as e:  # noqa: BLE001 — non-fatal auxiliary fetch
            partial_errors["queue_stats"] = str(e)

        pending_ids = [j.job_id for j in merged if j.state == "PENDING"]
        if pending_ids:
            try:
                details = fetch_pending_details(
                    session.ssh_client,
                    timeout=timeout,
                    include_all=include_all,
                )
                ranks = compute_queue_ranks(
                    session.ssh_client, pending_ids, timeout=timeout
                )
                for job in merged:
                    if job.state == "PENDING" and job.job_id in details:
                        info = details[job.job_id]
                        job.pending_reason = info.reason
                        job.priority = info.priority
                        job.qos = info.qos
                        job.submit_time = info.submit_time
                    if job.job_id in ranks:
                        job.queue_rank = ranks[job.job_id]
            except Exception as e:  # noqa: BLE001 — non-fatal
                partial_errors["pending_details"] = str(e)

        cluster_capacity: Optional[ClusterCapacity] = None
        partitions: list[PartitionStats] = []
        nodes_data: list[NodeStats] = []
        sinfo_fetched = False
        try:
            if now - session._sinfo_last_fetch > SINFO_REFRESH_SECONDS:
                cluster_capacity, partitions, nodes_data = fetch_sinfo(
                    session.ssh_client, timeout=timeout
                )
                sinfo_fetched = True
        except Exception as e:  # noqa: BLE001 — non-fatal
            partial_errors["sinfo"] = str(e)

        # Persist this cycle's jobs. Runs on the worker thread; any DB failure
        # is isolated as a partial error and never breaks live monitoring.
        jobs_for_history = merged
        if include_all:
            # When browsing the full cluster queue, do a second cheap squeue
            # pass for --me so the history DB does not ingest other users' jobs.
            jobs_for_history = list(sacct_jobs)
            try:
                my_active_jobs = fetch_squeue_jobs(
                    session.ssh_client,
                    timeout=timeout,
                    include_all=False,
                )
                jobs_for_history = merge_jobs(my_active_jobs, sacct_jobs)
            except Exception as e:  # noqa: BLE001 — non-fatal
                partial_errors["history_scope"] = str(e)

        if database is not None and repository is not None:
            try:
                with database.session() as db_session:
                    repository.capture_refresh(
                        db_session, profile_name, jobs_for_history, utcnow()
                    )
            except Exception as e:  # noqa: BLE001 — non-fatal
                partial_errors["db"] = str(e)

        return FetchResult(
            profile_name=profile_name,
            jobs=merged,
            queue_stats=queue_stats,
            cluster_capacity=cluster_capacity,
            partitions=partitions,
            nodes=nodes_data,
            sinfo_fetched=sinfo_fetched,
            partial_errors=partial_errors,
        )

    except (SSHConnectionError, SSHTimeoutError, SSHAuthenticationError) as e:
        return FetchResult(profile_name=profile_name, error=e)
    except Exception as e:  # noqa: BLE001 — keep the worker from dying silently
        # Surface unexpected errors through the normal error channel so the
        # connection strip shows them, rather than relying on the worker's
        # ``failed`` signal (which is harder to route the profile name through).
        return FetchResult(profile_name=profile_name, error=e)


class AppController(QObject):
    """Owns sessions, scheduling, and worker dispatch for the GUI.

    Signals carry the profile name so views can ignore updates for inactive
    profiles. Detached results are stored on the relevant :class:`ProfileSession`
    before the signal fires, so slots just read session state.
    """

    jobsUpdated = Signal(str)  # profile_name — jobs/queue/capacity refreshed
    connectionChanged = Signal(str)  # profile_name — loading / error state changed
    fetchFailed = Signal(str, str)  # profile_name, message
    authRequired = Signal(str)  # profile_name — SSH auth needs a credential
    activeProfileChanged = Signal(str)
    # profile_name, job_id, verb, ok, message
    jobActionFinished = Signal(str, str, str, bool, str)
    # profile_name, list[(job_id, name, state)] — jobs that just reached a
    # terminal state since the previous refresh.
    jobsFinished = Signal(str, list)

    def __init__(
        self,
        config: AppConfig,
        demo: bool = False,
        database: Optional[Database] = None,
        config_path: Optional[Path] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.demo = demo
        self.database = database
        self.config_path = config_path
        self.repository = Repository() if database is not None else None

        self.sessions: dict[str, ProfileSession] = {
            name: ProfileSession(profile, demo=demo)
            for name, profile in config.profiles.items()
        }
        self._active: Optional[str] = next(iter(self.sessions), None)
        self._timers: dict[str, QTimer] = {}
        self._util_timers: dict[str, QTimer] = {}

        # Filesystem snapshot cache (disabled in demo so fixtures never touch
        # the real config dir). Lives next to the config file.
        if demo:
            self._cache: Optional[SnapshotCache] = None
        else:
            base = config_path.parent if config_path else ConfigLoader.get_config_dir()
            self._cache = SnapshotCache(base / "cache")

        self._pool = QThreadPool.globalInstance()
        # Bound thread count so N profiles + auxiliary tasks never starve.
        self._pool.setMaxThreadCount(max(4, len(self.sessions) + 2))

    # ── profile selection ────────────────────────────────────────────
    @property
    def profile_names(self) -> list[str]:
        return list(self.sessions.keys())

    @property
    def active_profile(self) -> Optional[str]:
        return self._active

    def session(self, name: Optional[str] = None) -> Optional[ProfileSession]:
        return self.sessions.get(name or self._active or "")

    def set_active_profile(self, name: str) -> None:
        if name in self.sessions and name != self._active:
            self._active = name
            self.activeProfileChanged.emit(name)

    # ── lifecycle ────────────────────────────────────────────────────
    def start(self) -> None:
        """Paint cached state, then create refresh timers and kick a refresh."""
        self._load_cached_snapshots()
        for name in self.sessions:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda n=name: self.refresh_profile(n))
            self._timers[name] = timer
            self.refresh_profile(name)

        db_cfg = self.config.database
        if (
            self.database is not None
            and self.repository is not None
            and db_cfg.capture_utilization
            and db_cfg.utilization_interval > 0
        ):
            for name in self.sessions:
                timer = QTimer(self)
                timer.setInterval(int(db_cfg.utilization_interval * 1000))
                timer.timeout.connect(lambda n=name: self._capture_utilization(n))
                timer.start()
                self._util_timers[name] = timer

    def _load_cached_snapshots(self) -> None:
        """Populate sessions from disk so the UI has something to show at once."""
        if self._cache is None:
            return
        for name, session in self.sessions.items():
            snapshot = self._cache.load(name)
            if snapshot is None:
                continue
            session.jobs = snapshot.jobs
            session.queue_stats = snapshot.queue_stats
            session.cluster_capacity = snapshot.cluster_capacity
            session.partitions = snapshot.partitions
            session.nodes = snapshot.nodes
            session.last_updated = snapshot.cached_at
            session.is_cached = True
            # Leave _states_seen False so the first live refresh sets the
            # notification baseline silently (no alerts for jobs that finished
            # while the app was closed).
            self.connectionChanged.emit(name)
            self.jobsUpdated.emit(name)

    def shutdown(self) -> None:
        """Stop timers, close SSH connections, and release the database."""
        for timer in self._timers.values():
            timer.stop()
        for timer in self._util_timers.values():
            timer.stop()
        self._pool.waitForDone(2000)
        for session in self.sessions.values():
            session.close()
        if self.database is not None:
            self.database.close()

    # ── refresh dispatch ─────────────────────────────────────────────
    def refresh_profile(self, name: str) -> None:
        session = self.sessions.get(name)
        if session is None:
            return
        if session.action_in_progress or session.util_capture_in_progress:
            session.pending_refresh = True
            return
        if session.refresh_in_progress:
            return
        session.refresh_in_progress = True
        session.is_loading = True
        self.connectionChanged.emit(name)

        task = FetchTask(
            fetch_profile_data, session, name, self.database, self.repository
        )
        # Connect to a bound method (a QObject slot): with AutoConnection the
        # result is delivered to the main thread. A bare lambda has no receiver
        # QObject, so a cross-thread emit would not be queued onto this thread.
        task.signals.finished.connect(self._on_fetch_finished)
        self._pool.start(task)

    def force_refresh_active(self) -> None:
        """Manual refresh: drop the sacct cache so history re-fetches too."""
        name = self._active
        if name is None:
            return
        session = self.sessions.get(name)
        if session is not None:
            session._sacct_last_fetch = 0.0
        self.refresh_profile(name)

    def _on_fetch_finished(self, result: FetchResult) -> None:
        name = result.profile_name
        session = self.sessions.get(name)
        if session is None:
            return

        session.refresh_in_progress = False
        session.is_loading = False

        if result.error is not None:
            session.error_message = str(result.error)
            if (
                isinstance(result.error, SSHAuthenticationError)
                and session._auth_attempts < 3
            ):
                self.authRequired.emit(name)
            else:
                self.fetchFailed.emit(name, str(result.error))
            self.connectionChanged.emit(name)
        else:
            # Detect jobs that transitioned into a terminal state this cycle.
            transitions: list[tuple[str, str, str]] = []
            if session._states_seen:
                for job in result.jobs:
                    prev = session._prev_states.get(job.job_id)
                    if (
                        prev is not None
                        and prev not in TERMINAL_STATES
                        and job.state in TERMINAL_STATES
                    ):
                        transitions.append((job.job_id, job.name, job.state))
            session._prev_states = {j.job_id: j.state for j in result.jobs}
            session._states_seen = True

            session.jobs = result.jobs
            session.queue_stats = result.queue_stats
            if result.sinfo_fetched:
                session.cluster_capacity = result.cluster_capacity
                session.partitions = result.partitions
                session.nodes = result.nodes
                session._sinfo_last_fetch = time.time()
            session.last_updated = datetime.now().strftime("%H:%M:%S")
            session.error_message = None
            session.partial_errors = result.partial_errors
            session._auth_attempts = 0
            session.is_cached = False  # live data has now arrived
            self._save_snapshot(name, session)
            self.connectionChanged.emit(name)
            self.jobsUpdated.emit(name)
            if transitions:
                self.jobsFinished.emit(name, transitions)

        self._rearm(name)
        self._start_next_pending_action(name)

    def _save_snapshot(self, name: str, session: ProfileSession) -> None:
        """Persist the session's current displayable state for next launch."""
        if self._cache is None:
            return
        from datetime import datetime as _dt

        self._cache.save(
            CachedSnapshot(
                profile_name=name,
                cached_at=_dt.now().strftime("%Y-%m-%d %H:%M:%S"),
                jobs=list(session.jobs),
                queue_stats=session.queue_stats,
                cluster_capacity=session.cluster_capacity,
                partitions=list(session.partitions),
                nodes=list(session.nodes),
            )
        )

    def _rearm(self, name: str) -> None:
        timer = self._timers.get(name)
        session = self.sessions.get(name)
        if timer is not None and session is not None:
            timer.start(int(session.profile.refresh_interval * 1000))

    # ── measured utilization capture ────────────────────────────────
    def _capture_utilization(self, name: str) -> None:
        """Record measured GPU% / memory snapshots for running jobs.

        This runs on a slower cadence than the main refresh and is best-effort:
        any failure is swallowed so live monitoring is never disrupted.
        """
        session = self.sessions.get(name)
        if session is None:
            return
        if self.database is None or self.repository is None:
            return
        if session.refresh_in_progress or session.util_capture_in_progress:
            return
        if session.is_cached:
            return
        if not session.jobs:
            return

        session.util_capture_in_progress = True
        task = FetchTask(self._capture_utilization_work, session, name)
        task.signals.finished.connect(self._on_capture_utilization_done)
        self._pool.start(task)

    def _capture_utilization_work(
        self, session: ProfileSession, profile_name: str
    ) -> str:
        from slurmhub.slurm.scontrol import fetch_job_details

        running = [j for j in session.jobs if j.state == "RUNNING"]
        if not running or self.database is None or self.repository is None:
            return profile_name

        captured = utcnow()
        try:
            with self.database.session() as db_session:
                for job in running:
                    try:
                        details = fetch_job_details(
                            session.ssh_client,
                            job.job_id,
                            session.profile.ssh_timeout,
                        )
                    except Exception:  # noqa: BLE001 — best effort
                        details = None
                    pk = self.repository.upsert_job(
                        db_session, profile_name, job, details
                    )
                    self.repository.record_snapshot(
                        db_session, pk, job, captured, details
                    )
                db_session.commit()
        except Exception:  # noqa: BLE001 — never break the UI loop
            pass
        return profile_name

    def _on_capture_utilization_done(self, profile_name: str) -> None:
        session = self.sessions.get(profile_name)
        if session is not None:
            session.util_capture_in_progress = False
            self._start_next_pending_action(profile_name)
            if session.pending_refresh and not session.action_in_progress:
                session.pending_refresh = False
                self.refresh_profile(profile_name)

    # ── job actions (scancel / scontrol) ─────────────────────────────
    def run_job_command(
        self, profile_name: str, job_id: str, command: str, verb: str
    ) -> None:
        """Run a one-shot SSH command for a job on a worker thread.

        On success the active profile is refreshed so the new state shows up
        promptly. ``verb`` (``cancel`` / ``requeue`` / …) is echoed back via
        :data:`jobActionFinished` for the UI to report.
        """
        session = self.sessions.get(profile_name)
        if session is None:
            return
        if session.is_cached:
            # Showing stale cached data — refuse actions whose target state is
            # unknown until a live refresh confirms it.
            self.jobActionFinished.emit(
                profile_name, job_id, verb, False, "still loading live data"
            )
            return
        if session.refresh_in_progress:
            session.pending_actions.append((job_id, command, verb))
            session.pending_refresh = True
            self.connectionChanged.emit(profile_name)
            return
        if session.util_capture_in_progress:
            session.pending_actions.append((job_id, command, verb))
            session.pending_refresh = True
            self.connectionChanged.emit(profile_name)
            return
        if session.action_in_progress:
            session.pending_actions.append((job_id, command, verb))
            session.pending_refresh = True
            self.connectionChanged.emit(profile_name)
            return

        session.action_in_progress = True
        session.action_verb = verb
        session.action_job_id = job_id
        self.connectionChanged.emit(profile_name)

        timeout = session.profile.ssh_timeout
        client = session.ssh_client

        def _run() -> tuple[str, str, str, bool, str]:
            # The worker returns a fully-formed result tuple (catching its own
            # errors) so a single bound-method slot can handle it on the main
            # thread — see the note in refresh_profile about lambda receivers.
            try:
                client.execute(command, timeout=timeout)
                return (profile_name, job_id, verb, True, "")
            except Exception as exc:  # noqa: BLE001 — reported to the UI
                return (profile_name, job_id, verb, False, str(exc))

        task = FetchTask(_run)
        task.signals.finished.connect(self._on_action_result)
        self._pool.start(task)

    def cancel_job(self, profile_name: str, job_id: str) -> None:
        import shlex

        self.run_job_command(
            profile_name, job_id, f"scancel {shlex.quote(job_id)}", "cancel"
        )

    def requeue_job(self, profile_name: str, job_id: str) -> None:
        import shlex

        self.run_job_command(
            profile_name, job_id, f"scontrol requeue {shlex.quote(job_id)}", "requeue"
        )

    def hold_job(self, profile_name: str, job_id: str) -> None:
        import shlex

        self.run_job_command(
            profile_name, job_id, f"scontrol hold {shlex.quote(job_id)}", "hold"
        )

    def release_job(self, profile_name: str, job_id: str) -> None:
        import shlex

        self.run_job_command(
            profile_name, job_id, f"scontrol release {shlex.quote(job_id)}", "release"
        )

    def _on_action_result(self, result: tuple) -> None:
        profile_name, job_id, verb, ok, message = result
        session = self.sessions.get(profile_name)
        pending_refresh = False
        if session is not None:
            session.action_in_progress = False
            session.action_verb = ""
            session.action_job_id = ""
            pending_refresh = session.pending_refresh
            session.pending_refresh = False
            self.connectionChanged.emit(profile_name)

        self.jobActionFinished.emit(profile_name, job_id, verb, ok, message)
        if session is not None and session.pending_actions:
            self._start_next_pending_action(profile_name)
            return
        if ok or pending_refresh:
            self.refresh_profile(profile_name)

    def _start_next_pending_action(self, profile_name: str) -> None:
        session = self.sessions.get(profile_name)
        if session is None:
            return
        if (
            session.refresh_in_progress
            or session.util_capture_in_progress
            or session.action_in_progress
        ):
            return
        if not session.pending_actions:
            return
        job_id, command, verb = session.pending_actions.pop(0)
        self.run_job_command(profile_name, job_id, command, verb)

    # ── history maintenance ──────────────────────────────────────────
    def prune_history(self, retention_days: int) -> int:
        """Delete non-favourite runs older than ``retention_days``; return count.

        A local SQLite delete — fast enough to run inline from the Settings
        button. Favourites are always kept (see ``Repository.prune``).
        """
        if self.database is None or self.repository is None or retention_days <= 0:
            return 0
        with self.database.session() as db_session:
            return self.repository.prune(db_session, retention_days, utcnow())

    # ── auth ─────────────────────────────────────────────────────────
    def submit_credentials(self, name: str, password: Optional[str]) -> None:
        """Apply a password/passphrase entered by the user and re-refresh."""
        session = self.sessions.get(name)
        if session is None or password is None:
            return
        session.ssh_client.set_credentials(password=password, passphrase=password)
        session._auth_attempts += 1
        self.refresh_profile(name)
