#!/usr/bin/env python3
"""Helpers for the OCR backends used by the checked-in MinerU pipeline."""

from __future__ import annotations

import http.client
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from urllib import error, parse, request


BACKEND_OFFICIAL_API = "official-api"
BACKEND_SELF_HOSTED = "self-hosted"
DEFAULT_BACKEND = BACKEND_OFFICIAL_API
DEFAULT_API_BASE_URL = "https://mineru.net"
DEFAULT_MODEL_VERSION = "vlm"
DEFAULT_LANGUAGE = "ch"
DEFAULT_REQUEST_TIMEOUT = 60
DEFAULT_TASK_TIMEOUT = 3600
DEFAULT_POLL_INTERVAL = 5
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
DEFAULT_SELF_HOSTED_MODEL = "mineru"
SUPPORTED_BACKENDS = {BACKEND_OFFICIAL_API, BACKEND_SELF_HOSTED}


def resolve_backend(backend: str | None) -> str:
    value = (backend or DEFAULT_BACKEND).strip().lower()
    aliases = {
        "api": BACKEND_OFFICIAL_API,
        "official": BACKEND_OFFICIAL_API,
        "official-api": BACKEND_OFFICIAL_API,
        "official_api": BACKEND_OFFICIAL_API,
        "self-hosted": BACKEND_SELF_HOSTED,
        "self_hosted": BACKEND_SELF_HOSTED,
        "selfhosted": BACKEND_SELF_HOSTED,
    }
    resolved = aliases.get(value)
    if not resolved:
        supported = ", ".join(sorted(SUPPORTED_BACKENDS))
        raise RuntimeError(f"Unsupported MinerU backend: {backend!r}. Expected one of: {supported}")
    return resolved


def normalize_api_base_url(url: str | None) -> str:
    return (url or DEFAULT_API_BASE_URL).rstrip("/")


def normalize_self_hosted_url(url: str | None) -> str:
    return (url or "").rstrip("/") + "/"


def resolve_api_token(explicit_token: str | None) -> str:
    token = (
        explicit_token
        or os.environ.get("MINERU_API_TOKEN")
        or os.environ.get("MINERU_API_KEY")
        or os.environ.get("MINERU_VL_API_KEY")
        or ""
    ).strip()
    if not token:
        raise RuntimeError(
            "MinerU API token is required. Pass --api-token/--api-key or set MINERU_API_TOKEN."
        )
    return token


def resolve_self_hosted_url(explicit_url: str | None) -> str:
    url = (
        explicit_url
        or os.environ.get("MINERU_SELF_HOSTED_URL")
        or os.environ.get("MINERU_VL_SERVER")
        or ""
    ).strip()
    if not url:
        raise RuntimeError(
            "Self-hosted MinerU URL is required. Pass --server-url/--api-base-url or set MINERU_SELF_HOSTED_URL."
        )
    return normalize_self_hosted_url(url)


def resolve_self_hosted_token(explicit_token: str | None) -> str:
    token = (
        explicit_token
        or os.environ.get("MINERU_SELF_HOSTED_API_TOKEN")
        or os.environ.get("MINERU_SELF_HOSTED_API_KEY")
        or os.environ.get("MINERU_VL_API_KEY")
        or ""
    ).strip()
    if not token:
        raise RuntimeError(
            "Self-hosted MinerU API token is required. Pass --api-token/--api-key or set MINERU_SELF_HOSTED_API_TOKEN."
        )
    return token


def resolve_self_hosted_model(explicit_model: str | None) -> str:
    return (
        explicit_model
        or os.environ.get("MINERU_SELF_HOSTED_MODEL")
        or DEFAULT_SELF_HOSTED_MODEL
    ).strip()


def _decode_body(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def _http_error_message(exc: error.HTTPError) -> str:
    try:
        body = _decode_body(exc.read())
    except Exception:
        body = ""
    return f"HTTP {exc.code}: {body or exc.reason}"


def _request_bytes(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict | None = None,
    timeout: int = DEFAULT_REQUEST_TIMEOUT,
    retries: int = 5,
) -> bytes:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req_headers = dict(headers or {})
    if payload is not None:
        req_headers.setdefault("Content-Type", "application/json")
    req = request.Request(url, data=body, headers=req_headers, method=method)

    delay = 2.0
    for attempt in range(retries):
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except error.HTTPError as exc:
            if exc.code in RETRYABLE_STATUS_CODES and attempt < retries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 30.0)
                continue
            raise RuntimeError(_http_error_message(exc)) from exc
        except (error.URLError, TimeoutError, socket.timeout) as exc:
            if attempt < retries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 30.0)
                continue
            raise RuntimeError(f"Request failed for {url}: {exc}") from exc

    raise RuntimeError(f"Request failed for {url}")


def _request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict | None = None,
    timeout: int = DEFAULT_REQUEST_TIMEOUT,
    retries: int = 5,
) -> dict:
    raw = _request_bytes(
        url,
        method=method,
        headers=headers,
        payload=payload,
        timeout=timeout,
        retries=retries,
    )
    try:
        return json.loads(_decode_body(raw))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response from {url}: {_decode_body(raw)[:500]}") from exc


def _download_file(url: str, destination: Path, timeout: int = DEFAULT_REQUEST_TIMEOUT) -> None:
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as resp, destination.open("wb") as out:
            shutil.copyfileobj(resp, out)
    except error.HTTPError as exc:
        raise RuntimeError(f"Failed to download result zip: {_http_error_message(exc)}") from exc
    except (error.URLError, TimeoutError, socket.timeout) as exc:
        raise RuntimeError(f"Failed to download result zip: {exc}") from exc


def _upload_file_put(upload_url: str, file_path: str, timeout: int = DEFAULT_REQUEST_TIMEOUT) -> None:
    parsed = parse.urlparse(upload_url)
    request_path = parsed.path or "/"
    if parsed.query:
        request_path = f"{request_path}?{parsed.query}"

    connection_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = connection_cls(parsed.netloc, timeout=timeout)
    try:
        file_size = os.path.getsize(file_path)
        conn.putrequest("PUT", request_path)
        conn.putheader("Host", parsed.netloc)
        conn.putheader("Content-Length", str(file_size))
        conn.endheaders()

        with open(file_path, "rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                conn.send(chunk)

        response = conn.getresponse()
        body = _decode_body(response.read())
        if response.status not in (200, 201):
            raise RuntimeError(f"Upload failed with HTTP {response.status}: {body[:500]}")
    finally:
        conn.close()


def _api_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def _sanitize_data_id(file_path: str) -> str:
    stem = Path(file_path).stem
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in stem).strip("._-")
    if not safe:
        safe = "mineru"
    return f"{safe[:96]}_{int(time.time() * 1000)}"


def request_upload_url(
    file_path: str,
    *,
    api_base_url: str,
    api_token: str,
    model_version: str = DEFAULT_MODEL_VERSION,
    language: str = DEFAULT_LANGUAGE,
    enable_formula: bool = True,
    enable_table: bool = True,
    is_ocr: bool = True,
) -> tuple[str, str]:
    response = _request_json(
        f"{normalize_api_base_url(api_base_url)}/api/v4/file-urls/batch",
        method="POST",
        headers=_api_headers(api_token),
        payload={
            "files": [
                {
                    "name": Path(file_path).name,
                    "data_id": _sanitize_data_id(file_path),
                    "is_ocr": is_ocr,
                }
            ],
            "model_version": model_version,
            "language": language,
            "enable_formula": enable_formula,
            "enable_table": enable_table,
        },
    )
    if response.get("code") != 0:
        raise RuntimeError(f"MinerU create-upload request failed: {response.get('msg') or response}")

    data = response.get("data") or {}
    batch_id = data.get("batch_id")
    upload_urls = data.get("file_urls") or []
    if not batch_id or not upload_urls:
        raise RuntimeError(f"MinerU upload URL response missing fields: {response}")
    return batch_id, upload_urls[0]


def _pick_extract_result(result_data, file_name: str) -> dict | None:
    if isinstance(result_data, dict):
        return result_data
    if not isinstance(result_data, list):
        return None
    for item in result_data:
        if isinstance(item, dict) and item.get("file_name") == file_name:
            return item
    return result_data[0] if result_data else None


def poll_extract_result(
    batch_id: str,
    file_name: str,
    *,
    api_base_url: str,
    api_token: str,
    timeout_sec: int = DEFAULT_TASK_TIMEOUT,
    poll_interval_sec: int = DEFAULT_POLL_INTERVAL,
) -> dict:
    deadline = time.time() + timeout_sec
    url = f"{normalize_api_base_url(api_base_url)}/api/v4/extract-results/batch/{batch_id}"

    while time.time() < deadline:
        response = _request_json(url, headers=_api_headers(api_token))
        if response.get("code") != 0:
            raise RuntimeError(f"MinerU result polling failed: {response.get('msg') or response}")

        result = _pick_extract_result((response.get("data") or {}).get("extract_result"), file_name)
        if not result:
            time.sleep(poll_interval_sec)
            continue

        state = (result.get("state") or "").lower()
        if state == "done":
            return result
        if state == "failed":
            raise RuntimeError(result.get("err_msg") or f"MinerU extract failed for {file_name}")
        time.sleep(poll_interval_sec)

    raise RuntimeError(f"Timed out waiting for MinerU result for {file_name} (batch_id={batch_id})")


def _select_markdown_file(extracted_root: Path) -> Path:
    full_md_candidates = sorted(extracted_root.rglob("full.md"), key=lambda p: (len(p.parts), str(p)))
    if full_md_candidates:
        return full_md_candidates[0]

    md_candidates = sorted(extracted_root.rglob("*.md"), key=lambda p: (len(p.parts), str(p)))
    if md_candidates:
        return md_candidates[0]

    raise RuntimeError(f"MinerU result zip does not contain markdown output under {extracted_root}")


def materialize_result_zip(zip_path: Path, destination_root: str, stem: str) -> Path:
    with tempfile.TemporaryDirectory(prefix="mineru_zip_extract_") as tmp:
        extracted_root = Path(tmp) / "payload"
        extracted_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extracted_root)

        markdown_source = _select_markdown_file(extracted_root)
        payload_root = markdown_source.parent

        vlm_dir = Path(destination_root) / stem / "vlm"
        if vlm_dir.exists():
            shutil.rmtree(vlm_dir)
        vlm_dir.mkdir(parents=True, exist_ok=True)

        for child in payload_root.iterdir():
            target_name = f"{stem}.md" if child == markdown_source else child.name
            target = vlm_dir / target_name
            if child.is_dir():
                shutil.copytree(child, target)
            else:
                shutil.copy2(child, target)

        markdown_path = vlm_dir / f"{stem}.md"
        if not markdown_path.is_file():
            raise RuntimeError(f"MinerU result markdown missing after extract: {markdown_path}")
        return markdown_path


def run_official_ocr(
    file_path: str,
    output_dir: str,
    *,
    api_base_url: str,
    api_token: str,
    model_version: str = DEFAULT_MODEL_VERSION,
    language: str = DEFAULT_LANGUAGE,
    enable_formula: bool = True,
    enable_table: bool = True,
    is_ocr: bool = True,
    task_timeout_sec: int = DEFAULT_TASK_TIMEOUT,
    poll_interval_sec: int = DEFAULT_POLL_INTERVAL,
) -> dict:
    start_time = time.time()
    file_name = Path(file_path).name
    stem = Path(file_path).stem

    batch_id, upload_url = request_upload_url(
        file_path,
        api_base_url=api_base_url,
        api_token=api_token,
        model_version=model_version,
        language=language,
        enable_formula=enable_formula,
        enable_table=enable_table,
        is_ocr=is_ocr,
    )
    _upload_file_put(upload_url, file_path)
    result = poll_extract_result(
        batch_id,
        file_name,
        api_base_url=api_base_url,
        api_token=api_token,
        timeout_sec=task_timeout_sec,
        poll_interval_sec=poll_interval_sec,
    )

    full_zip_url = result.get("full_zip_url")
    if not full_zip_url:
        raise RuntimeError(f"MinerU finished without full_zip_url for {file_name}: {result}")

    with tempfile.TemporaryDirectory(prefix="mineru_result_") as tmp:
        zip_path = Path(tmp) / f"{stem}.zip"
        _download_file(full_zip_url, zip_path)
        markdown_path = materialize_result_zip(zip_path, output_dir, stem)

    elapsed = time.time() - start_time
    return {
        "file": file_path,
        "success": True,
        "error": None,
        "elapsed": elapsed,
        "markdown_path": str(markdown_path),
        "markdown_size": markdown_path.stat().st_size,
        "batch_id": batch_id,
    }


def run_self_hosted_ocr(
    file_path: str,
    output_dir: str,
    *,
    api_base_url: str,
    api_token: str,
    page_concurrency: int = 100,
    model_name: str = DEFAULT_SELF_HOSTED_MODEL,
    task_timeout_sec: int = DEFAULT_TASK_TIMEOUT,
) -> dict:
    start_time = time.time()
    stem = Path(file_path).stem

    env = os.environ.copy()
    env["MINERU_VL_API_KEY"] = api_token
    env["MINERU_VL_MAX_CONCURRENCY"] = str(page_concurrency)
    env.setdefault("MINERU_SELF_HOSTED_MODEL", model_name)

    cmd = [
        "mineru",
        "-p",
        file_path,
        "-o",
        output_dir,
        "-b",
        "vlm-http-client",
        "-u",
        normalize_self_hosted_url(api_base_url),
    ]
    proc = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        timeout=task_timeout_sec,
        check=False,
    )

    markdown_path = Path(output_dir) / stem / "vlm" / f"{stem}.md"
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(
            f"Self-hosted MinerU OCR failed for {Path(file_path).name} "
            f"(rc={proc.returncode}): {details[:800]}"
        )
    if not markdown_path.is_file():
        raise RuntimeError(f"Self-hosted MinerU OCR finished but markdown is missing: {markdown_path}")

    elapsed = time.time() - start_time
    return {
        "file": file_path,
        "success": True,
        "error": None,
        "elapsed": elapsed,
        "markdown_path": str(markdown_path),
        "markdown_size": markdown_path.stat().st_size,
        "backend": BACKEND_SELF_HOSTED,
        "model_name": model_name,
    }


def run_ocr(
    file_path: str,
    output_dir: str,
    *,
    backend: str,
    api_base_url: str | None,
    api_token: str | None,
    page_concurrency: int = 100,
    model_name: str | None = None,
    model_version: str = DEFAULT_MODEL_VERSION,
    language: str = DEFAULT_LANGUAGE,
    enable_formula: bool = True,
    enable_table: bool = True,
    is_ocr: bool = True,
    task_timeout_sec: int = DEFAULT_TASK_TIMEOUT,
    poll_interval_sec: int = DEFAULT_POLL_INTERVAL,
) -> dict:
    resolved_backend = resolve_backend(backend)
    if resolved_backend == BACKEND_SELF_HOSTED:
        return run_self_hosted_ocr(
            file_path,
            output_dir,
            api_base_url=resolve_self_hosted_url(api_base_url),
            api_token=resolve_self_hosted_token(api_token),
            page_concurrency=page_concurrency,
            model_name=resolve_self_hosted_model(model_name),
            task_timeout_sec=task_timeout_sec,
        )

    return run_official_ocr(
        file_path,
        output_dir,
        api_base_url=normalize_api_base_url(api_base_url),
        api_token=resolve_api_token(api_token),
        model_version=model_version,
        language=language,
        enable_formula=enable_formula,
        enable_table=enable_table,
        is_ocr=is_ocr,
        task_timeout_sec=task_timeout_sec,
        poll_interval_sec=poll_interval_sec,
    )
