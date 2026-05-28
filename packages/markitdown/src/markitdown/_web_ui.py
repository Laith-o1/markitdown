import cgi
import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import BinaryIO, Iterable, List, Optional

from ._markitdown import MarkItDown
from ._stream_info import StreamInfo


_PAGE_TITLE = "MarkItDown Web UI"


_HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MarkItDown Web UI</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #08111f;
      --bg-elevated: rgba(8, 17, 31, 0.78);
      --panel: rgba(12, 22, 40, 0.92);
      --panel-border: rgba(167, 190, 255, 0.14);
      --text: #eaf0ff;
      --muted: #93a4c7;
      --accent: #5ce1e6;
      --accent-strong: #7c8cff;
      --danger: #ff7b7b;
      --shadow: 0 30px 80px rgba(0, 0, 0, 0.35);
      --radius: 24px;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(92, 225, 230, 0.16), transparent 32%),
        radial-gradient(circle at top right, rgba(124, 140, 255, 0.18), transparent 28%),
        linear-gradient(145deg, #030712 0%, #08111f 46%, #0b172c 100%);
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
      background-size: 72px 72px;
      mask-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.65), transparent 90%);
    }

    .shell {
      position: relative;
      max-width: 1200px;
      margin: 0 auto;
      padding: 40px 20px 56px;
    }

    .hero {
      display: grid;
      gap: 14px;
      margin-bottom: 22px;
    }

    .eyebrow {
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--accent);
      font-size: 0.77rem;
      font-weight: 700;
    }

    h1 {
      margin: 0;
      font-size: clamp(2.2rem, 4vw, 4.7rem);
      line-height: 0.95;
      letter-spacing: -0.06em;
      max-width: 12ch;
    }

    .lede {
      margin: 0;
      max-width: 66ch;
      color: var(--muted);
      font-size: 1.04rem;
      line-height: 1.6;
    }

    .layout {
      display: grid;
      grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.25fr);
      gap: 18px;
      align-items: start;
    }

    .card {
      background: var(--bg-elevated);
      border: 1px solid var(--panel-border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
    }

    .dropzone {
      padding: 24px;
      min-height: 520px;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }

    .drop-target {
      border: 1.5px dashed rgba(124, 140, 255, 0.45);
      border-radius: 22px;
      padding: 28px;
      min-height: 260px;
      display: grid;
      place-items: center;
      text-align: center;
      transition: border-color 160ms ease, background-color 160ms ease, transform 160ms ease;
      background: linear-gradient(180deg, rgba(124, 140, 255, 0.08), rgba(92, 225, 230, 0.05));
    }

    .drop-target.dragover {
      border-color: var(--accent);
      transform: translateY(-1px);
      background: linear-gradient(180deg, rgba(92, 225, 230, 0.14), rgba(124, 140, 255, 0.12));
    }

    .drop-target strong {
      display: block;
      font-size: 1.15rem;
      margin-bottom: 10px;
    }

    .hint {
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
    }

    .controls {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }

    .button {
      appearance: none;
      border: 0;
      border-radius: 999px;
      padding: 12px 18px;
      background: linear-gradient(135deg, var(--accent), var(--accent-strong));
      color: #05111c;
      font-weight: 700;
      cursor: pointer;
      box-shadow: 0 12px 28px rgba(92, 225, 230, 0.22);
    }

    .button.secondary {
      color: var(--text);
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(255, 255, 255, 0.1);
      box-shadow: none;
    }

    .button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }

    .file-input {
      display: none;
    }

    .status {
      min-height: 24px;
      color: var(--muted);
      font-size: 0.95rem;
    }

    .status.error {
      color: var(--danger);
    }

    .results {
      display: grid;
      gap: 18px;
    }

    .result-card {
      padding: 18px;
      display: grid;
      gap: 14px;
      animation: rise 220ms ease-out;
    }

    .result-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
    }

    .result-title {
      font-size: 1rem;
      font-weight: 700;
      margin: 0;
    }

    .result-meta {
      color: var(--muted);
      font-size: 0.9rem;
    }

    .markdown {
      margin: 0;
      padding: 18px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.65;
      border-radius: 18px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      background: rgba(3, 9, 18, 0.68);
      max-height: 360px;
      min-height: 220px;
      color: #f5f7ff;
    }

    .error-box {
      padding: 16px 18px;
      border-radius: 18px;
      color: #ffd7d7;
      background: rgba(255, 123, 123, 0.14);
      border: 1px solid rgba(255, 123, 123, 0.25);
    }

    .empty-state {
      color: var(--muted);
      border: 1px dashed rgba(255, 255, 255, 0.11);
      border-radius: 18px;
      padding: 22px;
      text-align: center;
    }

    @keyframes rise {
      from {
        opacity: 0;
        transform: translateY(6px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    @media (max-width: 960px) {
      .layout {
        grid-template-columns: 1fr;
      }

      .dropzone {
        min-height: 0;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">MarkItDown</div>
      <h1>Drop files. Get Markdown.</h1>
      <p class="lede">Drag and drop one or more files, or click to choose them. The server uses the same MarkItDown conversion pipeline as the CLI and returns the Markdown directly in your browser.</p>
    </section>

    <section class="layout">
      <div class="card dropzone">
        <div id="drop-target" class="drop-target" role="button" tabindex="0" aria-label="Drop files here or click to browse">
          <div>
            <strong>Drop files here</strong>
            <p class="hint">Supported formats depend on the installed converters. Multiple files are processed in order.</p>
          </div>
        </div>

        <input id="file-input" class="file-input" type="file" multiple />

        <div class="controls">
          <button id="browse-button" class="button" type="button">Choose files</button>
          <button id="clear-button" class="button secondary" type="button">Clear results</button>
        </div>

        <div id="status" class="status">Waiting for files.</div>
      </div>

      <div class="card" style="padding: 24px; min-height: 520px;">
        <div class="result-header" style="margin-bottom: 16px;">
          <div>
            <p class="result-title">Converted output</p>
            <div class="result-meta">Markdown preview and per-file errors appear here.</div>
          </div>
        </div>
        <div id="results" class="results">
          <div class="empty-state">No files converted yet.</div>
        </div>
      </div>
    </section>
  </main>

  <script>
    const dropTarget = document.getElementById("drop-target");
    const fileInput = document.getElementById("file-input");
    const browseButton = document.getElementById("browse-button");
    const clearButton = document.getElementById("clear-button");
    const statusEl = document.getElementById("status");
    const resultsEl = document.getElementById("results");

    function setStatus(message, isError = false) {
      statusEl.textContent = message;
      statusEl.classList.toggle("error", isError);
    }

    function setIdleState() {
      resultsEl.innerHTML = '<div class="empty-state">No files converted yet.</div>';
      setStatus("Waiting for files.");
    }

    function downloadMarkdown(filename, markdown) {
      const baseName = (filename || "output").replace(/\.[^.]+$/, "");
      const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${baseName}.md`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    }

    function renderResults(items) {
      if (!items.length) {
        setIdleState();
        return;
      }

      resultsEl.innerHTML = "";
      for (const item of items) {
        const card = document.createElement("article");
        card.className = "card result-card";

        const header = document.createElement("div");
        header.className = "result-header";

        const titleGroup = document.createElement("div");

        const title = document.createElement("p");
        title.className = "result-title";
        title.textContent = item.filename || "Untitled file";

        const meta = document.createElement("div");
        meta.className = "result-meta";
        meta.textContent = item.error ? "Conversion failed" : `${item.bytes ?? 0} bytes processed`;

        titleGroup.appendChild(title);
        titleGroup.appendChild(meta);

        header.appendChild(titleGroup);

        if (item.error) {
          const errorBox = document.createElement("div");
          errorBox.className = "error-box";
          errorBox.textContent = item.error;
          card.appendChild(header);
          card.appendChild(errorBox);
          resultsEl.appendChild(card);
          continue;
        }

        const copyButton = document.createElement("button");
        copyButton.type = "button";
        copyButton.className = "button secondary";
        copyButton.textContent = "Copy Markdown";
        copyButton.addEventListener("click", async () => {
          await navigator.clipboard.writeText(item.markdown);
          copyButton.textContent = "Copied";
          window.setTimeout(() => {
            copyButton.textContent = "Copy Markdown";
          }, 1200);
        });

        header.appendChild(copyButton);

        const downloadButton = document.createElement("button");
        downloadButton.type = "button";
        downloadButton.className = "button secondary";
        downloadButton.textContent = "Download .md";
        downloadButton.addEventListener("click", () => {
          downloadMarkdown(item.filename, item.markdown);
        });

        header.appendChild(downloadButton);
        card.appendChild(header);

        const markdown = document.createElement("pre");
        markdown.className = "markdown";
        markdown.textContent = item.markdown;
        card.appendChild(markdown);
        resultsEl.appendChild(card);
      }
    }

    async function uploadFiles(files) {
      const fileList = Array.from(files || []);
      if (!fileList.length) {
        return;
      }

      setStatus(`Converting ${fileList.length} file${fileList.length === 1 ? "" : "s"}...`);
      browseButton.disabled = true;
      clearButton.disabled = true;

      try {
        const formData = new FormData();
        for (const file of fileList) {
          formData.append("files", file, file.name);
        }

        const response = await fetch("/convert", {
          method: "POST",
          body: formData,
        });

        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || "Conversion failed.");
        }

        renderResults(payload.results || []);
        setStatus(`Converted ${fileList.length} file${fileList.length === 1 ? "" : "s"}.`);
      } catch (error) {
        setStatus(error.message || String(error), true);
      } finally {
        browseButton.disabled = false;
        clearButton.disabled = false;
      }
    }

    dropTarget.addEventListener("click", () => fileInput.click());
    dropTarget.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        fileInput.click();
      }
    });

    browseButton.addEventListener("click", () => fileInput.click());
    clearButton.addEventListener("click", () => setIdleState());
    fileInput.addEventListener("change", () => uploadFiles(fileInput.files));

    dropTarget.addEventListener("dragenter", (event) => {
      event.preventDefault();
      dropTarget.classList.add("dragover");
    });

    dropTarget.addEventListener("dragover", (event) => {
      event.preventDefault();
      dropTarget.classList.add("dragover");
    });

    dropTarget.addEventListener("dragleave", (event) => {
      event.preventDefault();
      dropTarget.classList.remove("dragover");
    });

    dropTarget.addEventListener("drop", (event) => {
      event.preventDefault();
      dropTarget.classList.remove("dragover");
      uploadFiles(event.dataTransfer.files);
    });
  </script>
</body>
</html>
"""


class _MarkItDownWebServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(
        self,
        server_address,
        RequestHandlerClass,
        markitdown: MarkItDown,
        keep_data_uris: bool,
    ):
        super().__init__(server_address, RequestHandlerClass)
        self.markitdown = markitdown
        self.keep_data_uris = keep_data_uris


class _MarkItDownWebHandler(BaseHTTPRequestHandler):
    server: _MarkItDownWebServer

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self._send_html(_HTML_PAGE)
            return

        if self.path == "/healthz":
            self._send_text("ok")
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        if self.path != "/convert":
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return

        try:
            results = self._convert_uploaded_files()
        except ValueError as error:
            self._send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return
        except Exception as error:
            self._send_json({"error": str(error)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json({"results": results})

    def log_message(self, format: str, *args) -> None:
        return

    def _convert_uploaded_files(self) -> List[dict]:
        content_type = self.headers.get("content-type")
        if not content_type:
            raise ValueError("Missing content type.")

        if not content_type.startswith("multipart/form-data"):
            raise ValueError("Expected multipart form upload.")

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": self.headers.get("content-length", "0"),
            },
            keep_blank_values=True,
        )

        uploaded_items = list(_iter_uploaded_items(form))
        if not uploaded_items:
            raise ValueError("No files were uploaded.")

        results: List[dict] = []
        for item in uploaded_items:
            filename = _safe_filename(item.filename)
            stream_info = _build_stream_info(filename=filename, mimetype=item.type)
            try:
                result = self.server.markitdown.convert_stream(
                    item.file,
                    stream_info=stream_info,
                    keep_data_uris=self.server.keep_data_uris,
                )
            except Exception as error:
                results.append(
                    {
                        "filename": filename,
                        "error": str(error),
                        "bytes": _uploaded_size(item.file),
                    }
                )
                continue

            results.append(
                {
                    "filename": filename,
                    "markdown": result.markdown,
                    "bytes": _uploaded_size(item.file),
                }
            )

        return results

    def _send_html(self, content: str, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_text(self, content: str, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, payload: dict, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def serve_web_ui(
    markitdown: MarkItDown,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    keep_data_uris: bool = False,
) -> None:
    server = _MarkItDownWebServer(
        (host, port), _MarkItDownWebHandler, markitdown, keep_data_uris
    )
    actual_host, actual_port = server.server_address[:2]
    print(f"MarkItDown web UI running at http://{actual_host}:{actual_port}/", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _iter_uploaded_items(form: cgi.FieldStorage) -> Iterable[cgi.FieldStorage]:
  for value in form.list or []:
    if isinstance(value, cgi.FieldStorage) and value.filename:
      if value.name in {"files", "file"}:
        yield value


def _safe_filename(filename: Optional[str]) -> str:
    if not filename:
        return "upload"
    return os.path.basename(filename)


def _build_stream_info(*, filename: str, mimetype: Optional[str]) -> StreamInfo:
    extension = Path(filename).suffix.lower() or None
    if mimetype is None and filename:
        mimetype = mimetypes.guess_type(filename)[0]

    return StreamInfo(filename=filename, extension=extension, mimetype=mimetype)


def _uploaded_size(stream: BinaryIO) -> int:
    current = stream.tell() if stream.seekable() else None
    if stream.seekable():
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        if current is not None:
            stream.seek(current)
        return size

    return 0