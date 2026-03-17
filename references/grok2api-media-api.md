# Grok2API Media Reference

Use this reference only when the caller needs raw request shaping, endpoint-level defaults, or troubleshooting beyond the bundled Python CLI.

## Base settings

- Base URL: `GROK_MEDIA_BASE_URL`
- API key: `GROK_MEDIA_API_KEY`
- Auth header: `Authorization: Bearer <key>`
- Content types:
  - JSON for `/v1/images/generations`
  - JSON for `/v1/videos` text-to-video
  - `multipart/form-data` for `/v1/images/edits`
  - `multipart/form-data` for `/v1/videos` image-to-video

If a caller configures a base URL ending in `/v1`, normalize it back to the service root before appending endpoints. Otherwise requests can accidentally become `/v1/v1/images/generations`.

The CLI also accepts these fallback environment variables:

- `GROK2API_BASE_URL`
- `GROK2API_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_API_BASE`
- `OPENAI_API_KEY`

## Capability map

| Capability | Preferred endpoint | Notes |
| :-- | :-- | :-- |
| text-to-image | `POST /v1/images/generations` | Simple image-only path |
| image-to-image | `POST /v1/images/edits` | Upload one or more `image` parts |
| text-to-video | `POST /v1/videos` | JSON body |
| image-to-video | `POST /v1/videos` | Upload `input_reference`; only the first image is used |
| unified multimodal call | `POST /v1/chat/completions` | Use only when the caller explicitly wants chat-completions semantics |

## Default models

- Text to image: `grok-imagine-1.0`
- Image to image: `grok-imagine-1.0-edit`
- Video: `grok-imagine-1.0-video`

Override through CLI flags or environment variables:

- `--model`
- `GROK_MEDIA_IMAGE_MODEL`
- `GROK_MEDIA_IMAGE_EDIT_MODEL`
- `GROK_MEDIA_VIDEO_MODEL`

## Supported request shapes

### `POST /v1/images/generations`

```json
{
  "model": "grok-imagine-1.0",
  "prompt": "a cat floating in space",
  "n": 1,
  "size": "1024x1024",
  "response_format": "url"
}
```

Useful parameters:

- `n`: `1` to `10`
- `size`: `1280x720`, `720x1280`, `1792x1024`, `1024x1792`, `1024x1024`
- `response_format`: `url`, `b64_json`, `base64`

### `POST /v1/images/edits`

Multipart fields:

- `model=grok-imagine-1.0-edit`
- `prompt=<edit prompt>`
- one or more `image=@file`
- optional `n`, `size`, `response_format`

If more than three images are uploaded, Grok2API keeps only the last three.

### `POST /v1/videos`

Text-to-video JSON body:

```json
{
  "model": "grok-imagine-1.0-video",
  "prompt": "neon rainy street, slow tracking shot",
  "size": "1792x1024",
  "seconds": 18,
  "quality": "high"
}
```

Image-to-video multipart fields:

- `model=grok-imagine-1.0-video`
- `prompt=<video prompt>`
- `size=<video size>`
- `seconds=<6-30>`
- `quality=standard|high`
- `input_reference=@file`

Quality mapping from the upstream project:

- `standard` -> `480p`
- `high` -> `720p`

## Why the skill avoids `/v1/chat/completions` by default

The dedicated media endpoints are simpler and more reliable for other models:

- fewer payload branches
- no multimodal message array assembly
- no tool-call emulation concerns
- easier response downloading and artifact storage

Use `/v1/chat/completions` only when the caller explicitly needs the OpenAI chat-completions surface.

## Response handling notes

- Image endpoints commonly return `data[].url` or `data[].b64_json`.
- Video responses may return direct URLs or HTML wrappers, depending on upstream config.
- If returned URLs are not reachable from downstream tools, inspect upstream `app.app_url`.
- If the service still returns HTML for videos, the clean fix is upstream `app.video_format = url`.

## Troubleshooting

- `401` or `403`: verify the bearer token and Grok2API `api_key` value.
- asset download returns `403`: the service may be emitting internal or unsigned URLs; check `app.app_url` and proxy settings.
- video quality seems lower than expected: `high` may still begin from `480p` before an upstream upscale step.
- empty or partial output: inspect `response.json` and `summary.json` in the output folder before retrying.
