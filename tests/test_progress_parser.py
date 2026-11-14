import json

import pytest

from yt_dlp_gui.downloader import parse_progress_line


def _line(**data) -> str:
    return json.dumps(data)


def test_downloading_line():
    update = parse_progress_line(
        _line(
            status="downloading",
            downloaded_bytes=50,
            total_bytes=200,
            speed=1234.5,
            eta=7,
            _percent=25.0,
            _speed_str=" 1.20MiB/s",
            _eta_str="00:07",
            _total_bytes_str=" 200B",
            filename="/tmp/a.mp4",
        )
    )
    assert update is not None
    assert update.status == "downloading"
    assert update.percent == 25.0
    assert update.speed_text == "1.20MiB/s"
    assert update.eta_text == "00:07"
    assert update.total_text == "200B"
    assert update.filename == "/tmp/a.mp4"


def test_percent_computed_from_estimate():
    update = parse_progress_line(
        _line(status="downloading", downloaded_bytes=25, total_bytes_estimate=100)
    )
    assert update is not None
    assert update.total_bytes == 100
    assert update.percent == 25.0


def test_finished_line():
    update = parse_progress_line(
        _line(status="finished", downloaded_bytes=200, total_bytes=200, _percent=100.0)
    )
    assert update is not None
    assert update.status == "finished"
    assert update.percent == 100.0


@pytest.mark.parametrize(
    "line",
    [
        "",
        "not json",
        "{broken",
        "[]",
        '{"foo": "bar"}',
        '{"status": ""}',
        "__TITLE__Some title",
        "__FILE__/tmp/a.mp4",
        "ERROR: something went wrong",
    ],
)
def test_non_progress_lines_are_ignored(line):
    assert parse_progress_line(line) is None


def test_boolean_percent_is_not_accepted():
    update = parse_progress_line(
        _line(status="downloading", downloaded_bytes=10, total_bytes=40, _percent=True)
    )
    assert update is not None
    assert update.percent == 25.0
