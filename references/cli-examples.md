# Python CLI Examples

Use the bundled Python CLI instead of hand-writing HTTP calls.

## Required environment variables

```bash
export GROK_MEDIA_BASE_URL="http://127.0.0.1:8000"
export GROK_MEDIA_API_KEY="your-api-key"
```

If the configured base URL already ends with `/v1`, the CLI strips the extra suffix automatically.

## Text to image

```bash
python scripts/invoke_grok_media.py \
  --mode text-to-image \
  --prompt "cinematic cyberpunk city at night" \
  --size 1024x1024 \
  --count 1
```

## Image to image

```bash
python scripts/invoke_grok_media.py \
  --mode image-to-image \
  --prompt "turn this into a glossy poster" \
  --input-image ./input.png
```

## Text to video

```bash
python scripts/invoke_grok_media.py \
  --mode text-to-video \
  --prompt "neon rainy street, slow tracking shot" \
  --seconds 12 \
  --quality high \
  --size 1792x1024
```

## Image to video

```bash
python scripts/invoke_grok_media.py \
  --mode image-to-video \
  --prompt "subtle head turn and blink, slow push-in" \
  --input-image ./portrait.png \
  --seconds 8
```
