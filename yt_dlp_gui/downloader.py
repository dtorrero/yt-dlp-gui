"""yt-dlp process management and progress parsing.

Each download runs in its own :class:`QProcess` on Qt's event loop, so no
extra threads are needed.  yt-dlp is instructed to print one JSON object per
progress tick; the GUI only needs to react to ``job_changed`` signals.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import IO, Any

from PySide6.QtCore import QObject, QProcess, QStandardPaths, QTimer, Signal

from .settings import DEFAULT_PRESET, FORMAT_PRESETS, AppConfig

TITLE_MARKER = "__TITLE__"
FILE_MARKER = "__FILE__"


class JobStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"
    CANCELED = "canceled"

    @property
    def label(self) -> str:
        return {
            JobStatus.QUEUED: "Queued",
            JobStatus.DOWNLOADING: "Downloading",
            JobStatus.PROCESSING: "Processing",
            JobStatus.DONE: "Done",
            JobStatus.ERROR: "Failed",
            JobStatus.CANCELED: "Canceled",
        }[self]

    @property
    def is_terminal(self) -> bool:
        return self in (JobStatus.DONE, JobStatus.ERROR, JobStatus.CANCELED)


@dataclass
class ProgressUpdate:
    """Parsed contents of one ``--progress-template`` JSON line."""

    status: str
    percent: float | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed: float | None = None
    eta: int | None = None
    filename: str | None = None
    speed_text: str = ""
    eta_text: str = ""
    total_text: str = ""


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def parse_progress_line(line: str) -> ProgressUpdate | None:
    """Parse a progress JSON line emitted by yt-dlp.

    Returns ``None`` for anything that is not a progress object (regular log
    output, our marker lines, malformed JSON, ...).
    """
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    status = data.get("status")
    if not isinstance(status, str) or not status:
        return None

    downloaded = _as_int(data.get("downloaded_bytes"))
    total = _as_int(data.get("total_bytes")) or _as_int(data.get("total_bytes_estimate"))
    percent = _as_float(data.get("_percent"))
    if percent is None and downloaded is not None and total:
        percent = downloaded * 100.0 / total

    speed_text = data.get("_speed_str")
    eta_text = data.get("_eta_str")
    total_text = data.get("_total_bytes_str")

    return ProgressUpdate(
        status=status,
        percent=percent,
        downloaded_bytes=downloaded,
        total_bytes=total,
        speed=_as_float(data.get("speed")),
        eta=_as_int(data.get("eta")),
        filename=data.get("filename") if isinstance(data.get("filename"), str) else None,
        speed_text=speed_text.strip() if isinstance(speed_text, str) else "",
        eta_text=eta_text.strip() if isinstance(eta_text, str) else "",
        total_text=total_text.strip() if isinstance(total_text, str) else "",
    )


@dataclass
class DownloadJob:
    """One URL in the download queue."""

    id: str
    url: str
    title: str = ""
    status: JobStatus = JobStatus.QUEUED
    percent: float | None = None
    speed_text: str = ""
    eta_text: str = ""
    total_text: str = ""
    output_path: str = ""
    error: str = ""
    log_path: str = ""
    cancel_requested: bool = False

    @property
    def display_title(self) -> str:
        return self.title.strip() or self.url


def build_args(config: AppConfig, url: str, executable: str = "yt-dlp") -> list[str]:
    """Build the full yt-dlp argument list (never passed through a shell)."""
    preset = FORMAT_PRESETS.get(config.format_preset, FORMAT_PRESETS[DEFAULT_PRESET])
    download_dir = str(Path(config.download_dir).expanduser())
    args = [
        executable,
        "--no-warnings",
        "--no-simulate",
        "--progress",
        "--newline",
        "--progress-delta",
        "0.1",
        "--progress-template",
        "download:%(progress)j",
        "--print",
        f"before_dl:{TITLE_MARKER}%(title)s",
        "--print",
        f"after_move:{FILE_MARKER}%(filepath)s",
        "--paths",
        download_dir,
        "--output",
        config.filename_template or "%(title)s [%(id)s].%(ext)s",
    ]
    args.extend(str(argument) for argument in preset["arguments"])
    if not config.allow_playlist:
        args.append("--no-playlist")
    args.append(url)
    return args


def find_ytdlp(path_override: str = "") -> str:
    """Resolve the yt-dlp executable, honouring a configured path override."""
    if path_override:
        candidate = Path(path_override).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        found = shutil.which(path_override)
        return found or ""
    return shutil.which("yt-dlp") or ""


def find_ffmpeg() -> str:
    return shutil.which("ffmpeg") or ""


class DownloadManager(QObject):
    """Runs yt-dlp jobs, at most ``config.max_concurrent`` at a time."""

    job_added = Signal(str)
    job_changed = Signal(str)
    job_finished = Signal(str, bool)

    def __init__(self, config: AppConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self._jobs: dict[str, DownloadJob] = {}
        self._queue: list[str] = []
        self._processes: dict[str, QProcess] = {}
        self._logs: dict[str, IO[str]] = {}
        self._shutting_down = False
        self._executable = find_ytdlp(config.yt_dlp_path)

    # -- public API -----------------------------------------------------

    def get(self, job_id: str) -> DownloadJob | None:
        return self._jobs.get(job_id)

    def jobs(self) -> list[DownloadJob]:
        return list(self._jobs.values())

    def has_active_jobs(self) -> bool:
        return bool(self._processes)

    def update_config(self, config: AppConfig) -> None:
        self.config = config
        self._executable = find_ytdlp(config.yt_dlp_path)

    def enqueue(self, url: str) -> str:
        job_id = uuid.uuid4().hex[:8]
        job = DownloadJob(id=job_id, url=url)
        self._jobs[job_id] = job
        self._queue.append(job_id)
        self.job_added.emit(job_id)
        self._pump()
        return job_id

    def cancel(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None or job.status.is_terminal:
            return
        job.cancel_requested = True
        if job_id in self._queue:
            self._queue.remove(job_id)
            job.status = JobStatus.CANCELED
            self.job_changed.emit(job_id)
            self.job_finished.emit(job_id, False)
            return
        process = self._processes.get(job_id)
        if process is None:
            return
        job.status = JobStatus.CANCELED
        self.job_changed.emit(job_id)
        process.terminate()
        QTimer.singleShot(4000, lambda: self._kill_if_running(job_id))

    def remove(self, job_id: str) -> None:
        """Forget a finished job (used by the row's dismiss button)."""
        if job_id in self._processes or job_id in self._queue:
            return
        self._jobs.pop(job_id, None)

    def shutdown(self) -> None:
        self._shutting_down = True
        for job_id, process in list(self._processes.items()):
            if process.state() != QProcess.ProcessState.NotRunning:
                process.terminate()
                if not process.waitForFinished(1500):
                    process.kill()
                    process.waitForFinished(500)
            self._close_log(job_id)
            self._processes.pop(job_id, None)

    # -- queue ----------------------------------------------------------

    def _pump(self) -> None:
        limit = max(1, int(self.config.max_concurrent))
        while not self._shutting_down and len(self._processes) < limit and self._queue:
            job_id = self._queue.pop(0)
            job = self._jobs.get(job_id)
            if job is None or job.cancel_requested or job.status.is_terminal:
                continue
            if job.status != JobStatus.QUEUED:
                continue
            self._start(job)

    def _fail(self, job: DownloadJob, message: str) -> None:
        job.status = JobStatus.ERROR
        job.error = message
        job.speed_text = ""
        job.eta_text = ""
        self.job_changed.emit(job.id)
        self.job_finished.emit(job.id, False)

    def _start(self, job: DownloadJob) -> None:
        executable = find_ytdlp(self.config.yt_dlp_path) or self._executable
        if not executable:
            self._fail(
                job,
                "yt-dlp was not found. Install it (e.g. 'sudo pacman -S yt-dlp') "
                "or set its path in Settings.",
            )
            return
        self._executable = executable

        download_dir = Path(self.config.download_dir).expanduser()
        try:
            download_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._fail(job, f"Cannot use the download folder '{download_dir}': {exc}")
            return

        args = build_args(self.config, job.url, executable)
        job.status = JobStatus.DOWNLOADING
        job.error = ""
        job.percent = 0.0
        job.speed_text = ""
        job.eta_text = ""
        self._open_log(job)

        process = QProcess(self)
        process.setProgram(args[0])
        process.setArguments(args[1:])
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.setWorkingDirectory(str(download_dir))
        process.readyReadStandardOutput.connect(lambda job_id=job.id: self._read_output(job_id))
        process.finished.connect(
            lambda code, status, job_id=job.id: self._on_finished(job_id, code, status)
        )
        process.errorOccurred.connect(lambda error, job_id=job.id: self._on_error(job_id, error))
        self._processes[job.id] = process
        self.job_changed.emit(job.id)
        process.start()

    # -- process output -------------------------------------------------

    def _read_output(self, job_id: str) -> None:
        process = self._processes.get(job_id)
        job = self._jobs.get(job_id)
        if process is None or job is None:
            return
        changed = False
        while process.canReadLine():
            line = bytes(process.readLine()).decode("utf-8", "replace").rstrip("\r\n")
            if not line:
                continue
            self._write_log(job_id, line)
            if self._handle_line(job, line):
                changed = True
        if changed:
            self.job_changed.emit(job_id)

    def _handle_line(self, job: DownloadJob, line: str) -> bool:
        if line.startswith(TITLE_MARKER):
            title = line[len(TITLE_MARKER):].strip()
            if title:
                job.title = title
            return bool(title)
        if line.startswith(FILE_MARKER):
            path = line[len(FILE_MARKER):].strip()
            if path:
                job.output_path = path
            return bool(path)
        if line.startswith("ERROR:"):
            job.error = line
            job.status = JobStatus.ERROR
            return True
        if line.startswith(("[Merger]", "[ExtractAudio]", "[FixupM3u8]", "[VideoConvertor]")):
            job.status = JobStatus.PROCESSING
            return True
        update = parse_progress_line(line)
        if update is None:
            return False
        if update.status == "downloading":
            job.status = JobStatus.DOWNLOADING
            if update.percent is not None:
                job.percent = max(0.0, min(100.0, update.percent))
            job.speed_text = update.speed_text
            job.eta_text = update.eta_text
            job.total_text = update.total_text
            return True
        if update.status == "finished":
            job.percent = 100.0
            job.speed_text = ""
            job.eta_text = ""
            job.status = JobStatus.PROCESSING
            return True
        if update.status == "error":
            job.error = "yt-dlp reported a download error."
            job.status = JobStatus.ERROR
            return True
        return False

    def _on_finished(self, job_id: str, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        # Drain whatever yt-dlp wrote between the last readyRead and exiting;
        # the final __FILE__ marker usually arrives right before exit.
        self._read_output(job_id)
        process = self._processes.pop(job_id, None)
        self._close_log(job_id)
        job = self._jobs.get(job_id)
        if process is not None:
            process.deleteLater()
        if job is None:
            self._pump()
            return

        if job.cancel_requested:
            job.status = JobStatus.CANCELED
        elif job.error or exit_code != 0:
            job.status = JobStatus.ERROR
            if not job.error:
                job.error = f"yt-dlp exited with code {exit_code}."
        else:
            job.status = JobStatus.DONE
            if job.output_path:
                job.output_path = str(Path(job.output_path).expanduser())
        job.speed_text = ""
        job.eta_text = ""
        if job.status == JobStatus.DONE:
            job.percent = 100.0
        self.job_changed.emit(job_id)
        self.job_finished.emit(job_id, job.status == JobStatus.DONE)
        self._pump()

    def _on_error(self, job_id: str, error: QProcess.ProcessError) -> None:
        if error != QProcess.ProcessError.FailedToStart:
            return  # Crashed also emits finished(); _on_finished handles it.
        process = self._processes.pop(job_id, None)
        self._close_log(job_id)
        if process is not None:
            process.deleteLater()
        job = self._jobs.get(job_id)
        if job is None:
            self._pump()
            return
        job.error = "Failed to start yt-dlp. Check the binary path in Settings."
        job.status = JobStatus.ERROR
        job.speed_text = ""
        job.eta_text = ""
        self.job_changed.emit(job_id)
        self.job_finished.emit(job_id, False)
        self._pump()

    # -- logging --------------------------------------------------------

    def _open_log(self, job: DownloadJob) -> None:
        try:
            base = Path(
                QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
            )
            log_dir = base / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            path = log_dir / f"{stamp}-{job.id}.log"
            handle = path.open("w", encoding="utf-8")
            handle.write(f"# URL: {job.url}\n")
            handle.flush()
        except OSError:
            return
        self._logs[job.id] = handle
        job.log_path = str(path)

    def _write_log(self, job_id: str, line: str) -> None:
        handle = self._logs.get(job_id)
        if handle is None:
            return
        try:
            handle.write(line + "\n")
            handle.flush()
        except (OSError, ValueError):
            pass

    def _close_log(self, job_id: str) -> None:
        handle = self._logs.pop(job_id, None)
        if handle is None:
            return
        try:
            handle.close()
        except OSError:
            pass
