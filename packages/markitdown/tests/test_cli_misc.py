#!/usr/bin/env python3 -m pytest
import json
import sys
import socket
import subprocess
import time
import urllib.request
from markitdown import __version__

# This file contains CLI tests that are not directly tested by the FileTestVectors.
# This includes things like help messages, version numbers, and invalid flags.


def test_version() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "markitdown", "--version"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"CLI exited with error: {result.stderr}"
    assert __version__ in result.stdout, f"Version not found in output: {result.stdout}"


def test_invalid_flag() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "markitdown", "--foobar"],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0, f"CLI exited with error: {result.stderr}"
    assert (
        "unrecognized arguments" in result.stderr
    ), "Expected 'unrecognized arguments' to appear in STDERR"
    assert "SYNTAX" in result.stderr, "Expected 'SYNTAX' to appear in STDERR"


def _build_multipart_body(files, boundary: str) -> bytes:
    parts = []
    for field_name, filename, content, content_type in files:
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{filename}"\r\n'
            ).encode("utf-8")
        )
        parts.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        parts.append(content)
        parts.append(b"\r\n")

    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_web_ui_round_trip() -> None:
    port = _find_free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "markitdown",
            "--web",
            "--web-port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        deadline = time.time() + 20
        health_url = f"http://127.0.0.1:{port}/healthz"
        while time.time() < deadline:
            if process.poll() is not None:
                stderr = process.stderr.read() if process.stderr else ""
                raise AssertionError(f"Web UI exited early: {stderr}")

            try:
                with urllib.request.urlopen(health_url, timeout=1) as response:
                    if response.read().decode("utf-8") == "ok":
                        break
            except Exception:
                time.sleep(0.2)
        else:
            stderr = process.stderr.read() if process.stderr else ""
            raise AssertionError(f"Web UI did not start: {stderr}")

        boundary = "markitdown-web-test"
        body = _build_multipart_body(
            [("files", "example.txt", b"Hello from the web UI", "text/plain")],
            boundary,
        )
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/convert",
            data=body,
            method="POST",
        )
        request.add_header(
            "Content-Type", f"multipart/form-data; boundary={boundary}"
        )

        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))

        assert payload["results"][0]["filename"] == "example.txt"
        assert payload["results"][0]["markdown"] == "Hello from the web UI"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    """Runs this file's tests from the command line."""
    test_version()
    test_invalid_flag()
    print("All tests passed!")
