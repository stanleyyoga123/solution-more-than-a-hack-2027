"""Stream local assets and seekable media using bounded HTTP byte ranges."""

from http.server import BaseHTTPRequestHandler
import mimetypes
from pathlib import Path
import re


def parse_byte_range(value: str, size: int) -> tuple[int, int]:
    """Return an inclusive single range or raise for an unsatisfiable request."""
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
    if match is None or not any(match.groups()):
        raise ValueError("Expected a single byte range")
    first, last = match.groups()
    if not first:
        suffix = int(last)
        if suffix <= 0:
            raise ValueError("Suffix length must be positive")
        start = max(0, size - suffix)
        end = size - 1
    else:
        start = int(first)
        end = min(int(last), size - 1) if last else size - 1
    if start >= size or end < start:
        raise ValueError("Byte range is outside the file")
    return start, end


def send_file(handler: BaseHTTPRequestHandler, path: Path, send_body: bool) -> None:
    """Support GET/HEAD and the single ranges used by HTML video players."""
    size = path.stat().st_size
    range_header = handler.headers.get("Range")
    start, end = 0, size - 1
    if range_header:
        try:
            start, end = parse_byte_range(range_header, size)
        except ValueError:
            handler.send_response(416)
            handler.send_header("Content-Range", f"bytes */{size}")
            handler.send_header("Content-Length", "0")
            handler.end_headers()
            return

    handler.send_response(206 if range_header else 200)
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    handler.send_header("Content-Type", content_type)
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("Content-Length", str(end - start + 1))
    if range_header:
        handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    handler.end_headers()
    if not send_body:
        return

    remaining = end - start + 1
    with path.open("rb") as stream:
        stream.seek(start)
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            handler.wfile.write(chunk)
            remaining -= len(chunk)
