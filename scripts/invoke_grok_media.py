#!/usr/bin/env python3
"""
CLI wrapper for calling an existing Grok2API deployment for media generation.

This script intentionally avoids third-party dependencies so it can run inside
an existing Python or conda environment with only the standard library.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError


IMAGE_SIZES = {
    "1280x720",
    "720x1280",
    "1792x1024",
    "1024x1792",
    "1024x1024",
}
RESPONSE_FORMATS = {"url", "b64_json", "base64"}
VIDEO_QUALITIES = {"standard", "high"}
MODES = {"text-to-image", "image-to-image", "text-to-video", "image-to-video"}


@dataclass
class ResolvedConfig:
    base_url: str
    api_key: str
    model: str
    output_dir: Path


def first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def resolve_config(args: argparse.Namespace) -> ResolvedConfig:
    base_url = (
        args.base_url
        or first_env(
            "GROK_MEDIA_BASE_URL",
            "GROK2API_BASE_URL",
            "OPENAI_BASE_URL",
            "OPENAI_API_BASE",
        )
    )
    if not base_url:
        raise SystemExit("Missing base URL. Set GROK_MEDIA_BASE_URL or pass --base-url.")

    api_key = (
        args.api_key
        or first_env(
            "GROK_MEDIA_API_KEY",
            "GROK2API_API_KEY",
            "OPENAI_API_KEY",
        )
    )
    if not api_key:
        raise SystemExit("Missing API key. Set GROK_MEDIA_API_KEY or pass --api-key.")

    model = args.model or default_model(args.mode)
    output_dir = Path(args.output_dir) if args.output_dir else default_output_dir()
    return ResolvedConfig(
        base_url=normalize_base_url(base_url),
        api_key=api_key,
        model=model,
        output_dir=output_dir,
    )


def normalize_base_url(base_url: str) -> str:
    value = base_url.rstrip("/")
    if not value.endswith("/v1"):
        value = f"{value}/v1"
    return value


def default_model(mode: str) -> str:
    if mode == "text-to-image":
        return first_env("GROK_MEDIA_IMAGE_MODEL") or "grok-imagine-1.0"
    if mode == "image-to-image":
        return first_env("GROK_MEDIA_IMAGE_EDIT_MODEL") or "grok-imagine-1.0-edit"
    return first_env("GROK_MEDIA_VIDEO_MODEL") or "grok-imagine-1.0-video"


def default_output_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path.cwd() / "grok-media-output" / stamp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call an existing Grok2API deployment for image/video generation."
    )
    parser.add_argument("--mode", required=True, choices=sorted(MODES))
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--input-image", action="append", default=[])
    parser.add_argument("--base-url")
    parser.add_argument("--api-key")
    parser.add_argument("--model")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--size", default="1024x1024", choices=sorted(IMAGE_SIZES))
    parser.add_argument("--response-format", default="url", choices=sorted(RESPONSE_FORMATS))
    parser.add_argument("--seconds", type=int, default=8)
    parser.add_argument("--quality", default="standard", choices=sorted(VIDEO_QUALITIES))
    parser.add_argument("--output-dir")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.count < 1 or args.count > 10:
        raise SystemExit("--count must be between 1 and 10.")
    if args.seconds < 6 or args.seconds > 30:
        raise SystemExit("--seconds must be between 6 and 30.")
    if args.mode in {"image-to-image", "image-to-video"} and not args.input_image:
        raise SystemExit(f"--input-image is required for mode {args.mode}.")

    for image_path in args.input_image:
        if not Path(image_path).is_file():
            raise SystemExit(f"Input image not found: {image_path}")

    return args


def build_request(
    args: argparse.Namespace, config: ResolvedConfig
) -> tuple[str, bytes, dict[str, str], dict[str, Any]]:
    if args.mode == "text-to-image":
        endpoint = "/images/generations"
        payload = {
            "model": config.model,
            "prompt": args.prompt,
            "n": args.count,
            "size": args.size,
            "response_format": args.response_format,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        return endpoint, body, headers, payload

    if args.mode == "text-to-video":
        endpoint = "/videos"
        payload = {
            "model": config.model,
            "prompt": args.prompt,
            "size": args.size,
            "seconds": args.seconds,
            "quality": args.quality,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        return endpoint, body, headers, payload

    if args.mode == "image-to-image":
        endpoint = "/images/edits"
        fields = [
            ("model", config.model.encode("utf-8")),
            ("prompt", args.prompt.encode("utf-8")),
            ("n", str(args.count).encode("utf-8")),
            ("size", args.size.encode("utf-8")),
            ("response_format", args.response_format.encode("utf-8")),
        ]
        files = [("image", Path(path)) for path in args.input_image]
        content_type, body = encode_multipart(fields, files)
        preview = {
            "model": config.model,
            "prompt": args.prompt,
            "n": args.count,
            "size": args.size,
            "response_format": args.response_format,
            "image": [str(Path(path).resolve()) for path in args.input_image],
        }
        return endpoint, body, {"Content-Type": content_type}, preview

    endpoint = "/videos"
    fields = [
        ("model", config.model.encode("utf-8")),
        ("prompt", args.prompt.encode("utf-8")),
        ("size", args.size.encode("utf-8")),
        ("seconds", str(args.seconds).encode("utf-8")),
        ("quality", args.quality.encode("utf-8")),
    ]
    files = [("input_reference", Path(args.input_image[0]))]
    content_type, body = encode_multipart(fields, files)
    preview = {
        "model": config.model,
        "prompt": args.prompt,
        "size": args.size,
        "seconds": args.seconds,
        "quality": args.quality,
        "input_reference": str(Path(args.input_image[0]).resolve()),
    }
    return endpoint, body, {"Content-Type": content_type}, preview


def encode_multipart(
    fields: list[tuple[str, bytes]], files: list[tuple[str, Path]]
) -> tuple[str, bytes]:
    boundary = f"----grok-media-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                value,
                b"\r\n",
            ]
        )

    for field_name, path in files:
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{field_name}"; '
                    f'filename="{path.name}"\r\n'
                ).encode("utf-8"),
                f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
                path.read_bytes(),
                b"\r\n",
            ]
        )

    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return f"multipart/form-data; boundary={boundary}", b"".join(chunks)


def http_post(url: str, api_key: str, body: bytes, headers: dict[str, str]) -> str:
    req = request.Request(url=url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    for key, value in headers.items():
        req.add_header(key, value)

    try:
        with request.urlopen(req) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} {exc.reason}\n{detail}") from exc
    except URLError as exc:
        raise SystemExit(f"Request failed: {exc.reason}") from exc


def parse_response(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def collect_urls(value: Any, sink: set[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        sink.update(re.findall(r"https?://[^\s\"'<>]+", value))
        return
    if isinstance(value, dict):
        for nested in value.values():
            collect_urls(nested, sink)
        return
    if isinstance(value, list):
        for nested in value:
            collect_urls(nested, sink)


def collect_base64(value: Any, sink: list[dict[str, str | None]]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        match = re.match(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$", value)
        if match:
            sink.append({"mime": match.group("mime"), "data": match.group("data")})
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"b64_json", "base64"} and isinstance(nested, str):
                sink.append({"mime": None, "data": nested})
            else:
                collect_base64(nested, sink)
        return
    if isinstance(value, list):
        for nested in value:
            collect_base64(nested, sink)


def extension_for(mode: str, url: str | None = None, mime: str | None = None) -> str:
    if url:
        suffix = Path(url.split("?", 1)[0]).suffix
        if suffix:
            return suffix
    mime_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
    }
    if mime in mime_map:
        return mime_map[mime]
    return ".mp4" if "video" in mode else ".png"


def download_urls(urls: set[str], mode: str, output_dir: Path) -> list[dict[str, Any]]:
    saved: list[dict[str, Any]] = []
    for index, url in enumerate(sorted(urls), start=1):
        ext = extension_for(mode, url=url)
        target = output_dir / f"remote-{index}{ext}"
        try:
            with request.urlopen(url) as response:
                target.write_bytes(response.read())
            saved.append({"source": "url", "url": url, "path": str(target)})
        except Exception as exc:  # noqa: BLE001
            saved.append(
                {"source": "url", "url": url, "path": None, "error": str(exc)}
            )
    return saved


def decode_base64_entries(
    entries: list[dict[str, str | None]], mode: str, output_dir: Path
) -> list[dict[str, Any]]:
    saved: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        ext = extension_for(mode, mime=entry["mime"])
        target = output_dir / f"inline-{index}{ext}"
        target.write_bytes(base64.b64decode(entry["data"]))
        saved.append({"source": "base64", "path": str(target)})
    return saved


def main() -> int:
    args = parse_args()
    config = resolve_config(args)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    endpoint, body, headers, preview = build_request(args, config)
    url = f"{config.base_url}{endpoint}"

    if args.dry_run:
        print(
            json.dumps(
                {
                    "mode": args.mode,
                    "endpoint": endpoint,
                    "url": url,
                    "output_dir": str(config.output_dir),
                    "request": preview,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    raw_response = http_post(url, config.api_key, body, headers)
    response_path = config.output_dir / "response.json"
    response_path.write_text(raw_response, encoding="utf-8")

    parsed = parse_response(raw_response)
    urls: set[str] = set()
    base64_entries: list[dict[str, str | None]] = []
    collect_urls(parsed, urls)
    collect_base64(parsed, base64_entries)

    downloaded = download_urls(urls, args.mode, config.output_dir)
    embedded = decode_base64_entries(base64_entries, args.mode, config.output_dir)

    summary = {
        "mode": args.mode,
        "endpoint": endpoint,
        "url": url,
        "model": config.model,
        "output_dir": str(config.output_dir),
        "response_file": str(response_path),
        "downloaded": downloaded,
        "embedded": embedded,
        "response": parsed,
    }
    (config.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
