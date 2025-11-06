# VQGAN-CLIP Loop Generator - Deployment Guide

## Quick Start: Deploy to Modal

### 1. Deploy the Web API

```bash
modal deploy modal_video.py
```

This will output a URL like: `https://your-username--vqgan-clip-video-web.modal.run`

The deployment stays live even if you close your laptop!

---

## Usage: Submit Jobs via API

### Option 1: Using curl

```bash
# Submit a job
curl -X POST "https://your-username--vqgan-clip-video-web.modal.run/jobs/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "steampunk godzilla rotating in space",
    "num_frames": 120,
    "rotate_degrees": 3.0,
    "epochs": 3,
    "output_name": "godzilla.mp4"
  }'

# Response:
# {
#   "status": "submitted",
#   "job_id": "fc-abc123...",
#   "output_name": "godzilla.mp4",
#   "message": "Job submitted. Check status at /jobs/fc-abc123..."
# }
```

### Option 2: Using Python

```python
import requests

url = "https://your-username--vqgan-clip-video-web.modal.run"

# Submit job
response = requests.post(f"{url}/jobs/submit", json={
    "prompt": "steampunk godzilla rotating in space",
    "num_frames": 120,
    "rotate_degrees": 3.0,
    "epochs": 3,
    "output_name": "godzilla.mp4"
})

job = response.json()
print(f"Job ID: {job['job_id']}")

# Check status
import time
while True:
    status = requests.get(f"{url}/jobs/{job['job_id']}").json()
    print(f"Status: {status['status']}")

    if status['status'] == 'completed':
        print(f"Done! Video: {status['result']['filename']}")
        break

    time.sleep(60)  # Check every minute

# Download the video
video_response = requests.get(f"{url}/videos/godzilla.mp4")
with open("godzilla.mp4", "wb") as f:
    f.write(video_response.content)
```

---

## Available Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | string | **required** | Text description of the video |
| `output_name` | string | auto-generated | Output filename (must end in .mp4) |
| `num_frames` | int | 90 | Number of frames in the loop |
| `iterations_per_frame` | int | 50 | Quality (higher = better but slower) |
| `width` | int | 256 | Frame width in pixels |
| `height` | int | 256 | Frame height in pixels |
| `fps` | int | 30 | Frames per second |
| `seed` | int | null | Random seed (for reproducibility) |
| `zoom_scale` | float | 1.0 | Zoom per frame (>1.0 = zoom in, <1.0 = zoom out) |
| `pan_x` | int | 0 | Horizontal pan in pixels (positive = right) |
| `pan_y` | int | 0 | Vertical pan in pixels (positive = down) |
| `rotate_degrees` | float | 4.0 | Rotation per frame (360/num_frames for full rotation) |
| `epochs` | int | 3 | Refinement passes (2-5 recommended) |

---

## API Endpoints

### `POST /jobs/submit`
Submit a new video generation job (returns immediately with job_id)

### `GET /jobs/{job_id}`
Check the status of a job (returns "running" or "completed")

### `GET /videos`
List all generated videos in storage

### `GET /videos/{filename}`
Download a specific video

### `DELETE /videos/{filename}`
Delete a video from storage

---

## Local Testing (Before Deployment)

You can test locally with `modal run`:

```bash
# For quick local jobs (will fail if connection drops)
modal run modal_video.py::submit_loop_job \
  --prompt "test video" \
  --num-frames 30 \
  --epochs 2

# List videos
modal run modal_video.py::list_videos_cli

# Download video
modal run modal_video.py::download_video_cli --filename test_video.mp4
```

---

## Example: Perfect 360° Rotation Loop

```bash
curl -X POST "https://your-url/jobs/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a mystical mandala in deep space",
    "num_frames": 90,
    "rotate_degrees": 4.0,
    "epochs": 3,
    "width": 512,
    "height": 512,
    "fps": 30
  }'
```

This creates a 3-second perfect loop with a complete 360° rotation (90 frames × 4° = 360°).

---

## Tips

- **Disconnection-proof**: Once deployed, jobs survive internet disconnections
- **Storage**: Videos stay in Modal storage until you delete them
- **Check status**: Poll `/jobs/{job_id}` to monitor progress
- **Long jobs**: Set `num_frames` high and `epochs` to 3-5 for best quality loops
- **Rotation**: For perfect 360° rotation, use `rotate_degrees = 360 / num_frames`
