import json

from yt_dlp_gui.downloader import DownloadJob, DownloadManager, JobStatus
from yt_dlp_gui.settings import AppConfig


def _manager() -> DownloadManager:
    config = AppConfig(download_dir="/tmp/yt-dlp-gui-tests")
    return DownloadManager(config)


def test_title_and_file_markers(qapp):
    manager = _manager()
    job = DownloadJob(id="abc", url="https://example.com/v")
    manager._jobs[job.id] = job

    assert manager._handle_line(job, "__TITLE__My video") is True
    assert job.title == "My video"
    assert manager._handle_line(job, "__FILE__/tmp/My video.mp4") is True
    assert job.output_path == "/tmp/My video.mp4"


def test_progress_line_updates_job(qapp):
    manager = _manager()
    job = DownloadJob(id="abc", url="https://example.com/v")
    line = json.dumps(
        {
            "status": "downloading",
            "downloaded_bytes": 50,
            "total_bytes": 100,
            "_percent": 50.0,
            "_speed_str": " 1.00MiB/s",
            "_eta_str": "00:03",
            "_total_bytes_str": " 100B",
        }
    )
    assert manager._handle_line(job, line) is True
    assert job.status == JobStatus.DOWNLOADING
    assert job.percent == 50.0
    assert job.speed_text == "1.00MiB/s"

    finished = json.dumps({"status": "finished", "_percent": 100.0})
    assert manager._handle_line(job, finished) is True
    assert job.status == JobStatus.PROCESSING
    assert job.percent == 100.0


def test_error_line_sets_failed_state(qapp):
    manager = _manager()
    job = DownloadJob(id="abc", url="https://example.com/v")
    assert manager._handle_line(job, "ERROR: Video unavailable") is True
    assert job.status == JobStatus.ERROR
    assert "Video unavailable" in job.error


def test_unknown_lines_are_ignored(qapp):
    manager = _manager()
    job = DownloadJob(id="abc", url="https://example.com/v")
    assert manager._handle_line(job, "[youtube] Extracting URL") is False
    assert job.status == JobStatus.QUEUED


def test_missing_ytdlp_fails_job(monkeypatch, qapp):
    monkeypatch.setattr("yt_dlp_gui.downloader.find_ytdlp", lambda path="": "")
    manager = _manager()
    manager._executable = ""
    events = []
    manager.job_finished.connect(lambda job_id, ok: events.append((job_id, ok)))

    job_id = manager.enqueue("https://example.com/v")
    job = manager.get(job_id)
    assert job is not None
    assert job.status == JobStatus.ERROR
    assert "yt-dlp" in job.error
    assert events == [(job_id, False)]
