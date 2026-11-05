"""HTTP routes for the local tracking comparison app."""

from http.server import BaseHTTPRequestHandler
import json
import logging
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from frontend.server.file_response import send_file
from frontend.server.experiment_store import load_experiments
from frontend.server.quality_report_store import empty_quality_report
from frontend.server.tracking_store import TrackingStore

_LOGGER = logging.getLogger(__name__)


class RequestHandler(BaseHTTPRequestHandler):
    def __init__(
        self,
        *args,
        store: TrackingStore,
        metadata: dict,
        video: Path,
        web_dir: Path,
        birdseye_video: Path | None = None,
        quality_body: bytes | None = None,
        diagnostics_body: bytes | None = None,
        experiment_registry: Path | None = None,
        **kwargs,
    ):
        self._experiment_registry = (
            experiment_registry or Path(__file__).resolve().parents[2] / "experiments"
        )
        self._store = store
        self._metadata = metadata
        self._video = video
        self._birdseye_video = birdseye_video
        self._diagnostics_body = diagnostics_body
        self._quality_body = quality_body
        self._web_dir = web_dir.resolve()
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        self._dispatch(send_body=True)

    def do_HEAD(self) -> None:
        self._dispatch(send_body=False)

    def _dispatch(self, send_body: bool) -> None:
        try:
            self._route(send_body)
        except (BrokenPipeError, ConnectionResetError):
            # Seeking cancels previous video downloads in normal browser use.
            _LOGGER.debug("Browser cancelled a response")

    def _route(self, send_body: bool) -> None:
        url = urlsplit(self.path)
        if url.path == "/api/experiments":
            try:
                payload = load_experiments(self._experiment_registry)
            except (OSError, ValueError):
                _LOGGER.exception("Unable to load experiment registry")
                self.send_error(
                    503,
                    "Experiment registry unavailable; check the server logs and retry",
                )
                return
            self._send_json(payload, send_body)
            return
        if url.path == "/api/diagnostics":
            if self._diagnostics_body is None:
                self._send_json({"available": False}, send_body)
            else:
                self._send_json_body(self._diagnostics_body, send_body)
            return
        if url.path == "/api/metadata":
            self._send_json(self._metadata, send_body)
            return
        if url.path == "/api/quality":
            if self._quality_body is None:
                self._send_json(empty_quality_report(), send_body)
            else:
                self._send_json_body(self._quality_body, send_body)
            return
        if url.path == "/api/frames":
            try:
                start, count = self._frame_window(url.query)
            except ValueError as error:
                self.send_error(400, str(error))
                return
            frames = self._store.read_frames(start, count)
            self._send_json({"frames": frames}, send_body)
            return
        if url.path == "/video":
            send_file(self, self._video, send_body)
            return
        if url.path == "/birdseye-video":
            if self._birdseye_video is None:
                self.send_error(404, "Bird's-eye video is not configured")
                return
            send_file(self, self._birdseye_video, send_body)
            return

        relative = unquote(url.path).lstrip("/") or "index.html"
        asset = (self._web_dir / relative).resolve()
        if not asset.is_relative_to(self._web_dir) or not asset.is_file():
            self.send_error(404, "Asset not found")
            return
        send_file(self, asset, send_body)

    def _frame_window(self, query: str) -> tuple[int, int]:
        values = parse_qs(query, keep_blank_values=True)
        try:
            start = int(values.get("start", ["0"])[0])
            count = int(values.get("count", ["1"])[0])
        except ValueError:
            raise ValueError("start and count must be integers") from None
        frame_count = self._metadata["frame_count"]
        if not 0 <= start < frame_count:
            raise ValueError(f"start must be between 0 and {frame_count - 1}")
        if not 1 <= count <= 250:
            raise ValueError("count must be between 1 and 250")
        return start, min(count, frame_count - start)

    def _send_json(self, payload: dict, send_body: bool) -> None:
        body = json.dumps(payload, allow_nan=False, separators=(",", ":")).encode()
        self._send_json_body(body, send_body)

    def _send_json_body(self, body: bytes, send_body: bool) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        _LOGGER.debug("HTTP %s", format % args)
