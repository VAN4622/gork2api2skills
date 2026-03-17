---
name: grok-media-api
description: Call an existing Grok2API deployment for text-to-image, image-to-image, text-to-video, and image-to-video generation, then save returned media locally. Use when Codex or another model needs a thin Grok media invocation skill for openclaw or other model-tool integrations, especially when the goal is to wrap already-deployed HTTP endpoints like `/v1/images/generations`, `/v1/images/edits`, and `/v1/videos` rather than deploy or debug grok2api itself.
---

# Grok Media API

## Overview

Treat Grok2API as already deployed and reachable. Stay focused on invocation and output handling unless the user explicitly asks to debug the upstream service.

Use the bundled Python CLI at `scripts/invoke_grok_media.py` as the default entrypoint. It standardizes auth, multipart upload, output directories, response capture, and media downloads for other models.

## Quick Start

Set these environment variables first:

- `GROK_MEDIA_BASE_URL`
- `GROK_MEDIA_API_KEY`
- Optional: `GROK_MEDIA_IMAGE_MODEL`, `GROK_MEDIA_IMAGE_EDIT_MODEL`, `GROK_MEDIA_VIDEO_MODEL`

Run the CLI from the skill directory or pass absolute paths:

```bash
python scripts/invoke_grok_media.py \
  --mode text-to-image \
  --prompt "cinematic cyberpunk city at night"
```

```bash
python scripts/invoke_grok_media.py \
  --mode image-to-image \
  --prompt "turn this into a glossy poster" \
  --input-image ./input.png
```

```bash
python scripts/invoke_grok_media.py \
  --mode text-to-video \
  --prompt "neon rainy street, slow tracking shot" \
  --seconds 12 \
  --quality high
```

```bash
python scripts/invoke_grok_media.py \
  --mode image-to-video \
  --prompt "subtle head turn and blink, slow push-in" \
  --input-image ./portrait.png \
  --seconds 8
```

The CLI creates a timestamped output folder, stores the raw API response, downloads returned URLs when possible, and prints a JSON summary for downstream model steps.

## Endpoint Choice

- Use `text-to-image` for `POST /v1/images/generations`
- Use `image-to-image` for `POST /v1/images/edits`
- Use `text-to-video` for `POST /v1/videos`
- Use `image-to-video` for `POST /v1/videos` with `input_reference`
- Use `/v1/chat/completions` only when the user explicitly wants the unified multimodal chat surface

## Workflow

1. Confirm the user wants a wrapper over an existing Grok2API deployment.
2. Collect `mode`, `prompt`, and `input-image` when the mode needs a reference image.
3. Prefer the Python CLI over hand-written HTTP calls.
4. Inspect the emitted `summary.json` and saved outputs before chaining more work.
5. Read `references/grok2api-media-api.md` only when raw payload shaping is necessary.

## Operating Notes

- Prefer non-streaming requests for stable file outputs.
- Expect `image-to-video` to use only the first reference image.
- Expect `/v1/images/edits` to keep only the last three input images if too many are sent.
- If video results come back as HTML wrappers instead of direct asset URLs, the upstream Grok2API config may still be using `app.video_format = html`.
- If returned asset URLs are unreachable or return `403`, check the upstream `app.app_url`.

## Resources

- Use `scripts/invoke_grok_media.py` for the primary CLI workflow.
- Read `references/cli-examples.md` for ready-to-run examples.
- Read `references/grok2api-media-api.md` for endpoint details and troubleshooting.
