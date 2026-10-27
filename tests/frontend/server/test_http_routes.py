from functools import partial
from contextlib import closing
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from threading import Thread

import pytest

from frontend.server.request_handler import RequestHandler
from frontend.server.tracking_store import TrackingStore


@pytest.fixture
def viewer_server(tmp_path):
    tracking = tmp_path / "tracking.csv"
    tracking.write_text(
        "frame,entity_id,entity_type,team_id,pos_x,pos_y,position_valid\n"
        "0,ball,ball,,0.2,0.3,True\n"
        "1,ball,ball,,,,False\n"
    )
    store = TrackingStore(tracking, tracking, tmp_path / "cache", 2)
    video = tmp_path / "video.mp4"
    video.write_bytes(b"0123456789")
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<title>Viewer</title>")
    metadata = {"frame_count": 2, "fps": 25, "video_url": "/video"}
    handler = partial(
        RequestHandler, store=store, metadata=metadata, video=video, web_dir=web
    )
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_port
        finally:
            server.shutdown()
            thread.join()


def request(port, path, method="GET", headers=None):
    with closing(HTTPConnection("127.0.0.1", port, timeout=3)) as connection:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()


@pytest.mark.parametrize(
    ("value", "body", "content_range"),
    [
        ("bytes=2-4", b"234", "bytes 2-4/10"),
        ("bytes=7-", b"789", "bytes 7-9/10"),
        ("bytes=-3", b"789", "bytes 7-9/10"),
        ("bytes=8-99", b"89", "bytes 8-9/10"),
    ],
)
def test_video_byte_ranges_return_only_requested_bytes(
    viewer_server, value, body, content_range
):
    status, headers, contents = request(
        viewer_server, "/video", headers={"Range": value}
    )
    assert status == 206
    assert contents == body
    assert headers["Content-Range"] == content_range
    assert int(headers["Content-Length"]) == len(body)


@pytest.mark.parametrize(
    "value", ["bytes=10-", "bytes=5-3", "bytes=-0", "bytes=0-1,3-4"]
)
def test_video_rejects_unsatisfiable_or_multiple_ranges(viewer_server, value):
    status, headers, contents = request(
        viewer_server, "/video", headers={"Range": value}
    )
    assert status == 416
    assert headers["Content-Range"] == "bytes */10"
    assert contents == b""


def test_video_head_preserves_range_headers_without_body(viewer_server):
    status, headers, contents = request(
        viewer_server, "/video", method="HEAD", headers={"Range": "bytes=2-4"}
    )
    assert status == 206
    assert headers["Content-Length"] == "3"
    assert contents == b""


def test_api_limits_windows_and_keeps_empty_frames(viewer_server):
    status, _, contents = request(viewer_server, "/api/frames?start=0&count=250")
    assert status == 200
    frames = json.loads(contents)["frames"]
    assert [frame["frame"] for frame in frames] == [0, 1]
    assert frames[1] == {"frame": 1, "pixels": [], "normalized": []}

    for query in ["start=-1", "start=2", "count=251", "count=0", "start=abc"]:
        status, _, _ = request(viewer_server, f"/api/frames?{query}")
        assert status == 400


def test_static_routes_do_not_expose_files_outside_web_directory(viewer_server):
    assert request(viewer_server, "/")[0] == 200
    assert request(viewer_server, "/%2e%2e/tracking.csv")[0] == 404
    status, _, contents = request(viewer_server, "/api/metadata")
    assert status == 200
    assert json.loads(contents)["fps"] == 25
