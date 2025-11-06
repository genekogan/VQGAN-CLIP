# VQGAN-CLIP Modal Deployment Guide

Generate stunning AI videos and images using VQGAN+CLIP, deployed on Modal for reliable, disconnect-proof processing.

## 🚀 Quick Start

### 1. Deploy to Modal

```bash
modal deploy modal_video.py
```

This creates a persistent API at: `https://your-username--vqgan-clip-video-web.modal.run`

**Your API URL:** `https://edenartlab--vqgan-clip-video-web.modal.run`

---

## 📸 Generate Images

### Using modal run (local, quick tests)

```bash
modal run modal_simple.py --prompt "steampunk godzilla"
```

Output: `output.png` in current directory

**Options:**
- `--prompt "your prompt"` - Description of the image
- `--iterations 500` - Quality (higher = better, default: 500)
- `--size 512 512` - Width and height in pixels
- `--seed 42` - Random seed for reproducibility
- `--output myimage.png` - Custom output filename

---

## 🎥 Generate Videos (Standard)

### Method 1: Local (fails if disconnected)

```bash
modal run modal_video.py --prompt "Buddha at a rave" --num-frames 30 --rotate-degrees 12
```

### Method 2: Remote API (survives disconnects) ✅ RECOMMENDED

```bash
curl -X POST "https://edenartlab--vqgan-clip-video-web.modal.run/jobs/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Buddha at a rave",
    "num_frames": 30,
    "rotate_degrees": 12,
    "width": 512,
    "height": 512,
    "fps": 30
  }'
```

**Response:**
```json
{
  "status": "submitted",
  "job_id": "fc-abc123...",
  "output_name": "Buddha_at_a_rave_1234567890.mp4",
  "message": "Job submitted. Check status at /jobs/fc-abc123..."
}
```

---

## 🔁 Generate Perfect Loops

Perfect loops use epoch-based interpolation to ensure the last frame seamlessly transitions to the first frame.

### Submit a Loop Job

```bash
curl -X POST "https://edenartlab--vqgan-clip-video-web.modal.run/jobs/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "mystical mandala rotating through space",
    "num_frames": 90,
    "rotate_degrees": 4.0,
    "epochs": 3,
    "width": 512,
    "height": 512,
    "fps": 30
  }'
```

**For perfect 360° rotation:** `rotate_degrees = 360 / num_frames`
- 90 frames: `rotate_degrees: 4.0`
- 120 frames: `rotate_degrees: 3.0`
- 60 frames: `rotate_degrees: 6.0`

---

## 📦 Download Results

### 1. Check Job Status

```bash
curl "https://edenartlab--vqgan-clip-video-web.modal.run/jobs/fc-abc123..."
```

**Response when running:**
```json
{
  "status": "running",
  "job_id": "fc-abc123...",
  "message": "Job is still processing"
}
```

**Response when complete:**
```json
{
  "status": "completed",
  "job_id": "fc-abc123...",
  "result": {
    "status": "success",
    "filename": "mystical_mandala_1234567890.mp4",
    "size_mb": 12.5
  }
}
```

### 2. List All Videos

```bash
curl "https://edenartlab--vqgan-clip-video-web.modal.run/videos"
```

**Response:**
```json
{
  "videos": [
    {
      "filename": "mystical_mandala_1234567890.mp4",
      "size_mb": 12.5,
      "modified": 1762464674.0
    }
  ],
  "count": 1
}
```

### 3. Download Video

```bash
curl "https://edenartlab--vqgan-clip-video-web.modal.run/videos/mystical_mandala_1234567890.mp4" \
  -o mystical_mandala.mp4
```

Or download directly in browser:
```
https://edenartlab--vqgan-clip-video-web.modal.run/videos/mystical_mandala_1234567890.mp4
```

### 4. Delete Video (Optional)

```bash
curl -X DELETE "https://edenartlab--vqgan-clip-video-web.modal.run/videos/mystical_mandala_1234567890.mp4"
```

---

## 🎨 Parameters Reference

### Common Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | string | **required** | Text description of what to generate |
| `width` | int | 256 | Frame width (256, 512, 768, 1024) |
| `height` | int | 256 | Frame height (256, 512, 768, 1024) |
| `seed` | int | random | Random seed for reproducibility |

### Image-Only Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `iterations` | int | 500 | Optimization steps (more = better quality) |
| `output` | string | "output.png" | Output filename |

### Video Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `num_frames` | int | 20 | Number of frames to generate |
| `iterations_per_frame` | int | 50 | Quality per frame |
| `fps` | int | 10 | Frames per second |
| `output_name` | string | auto | Custom filename (optional) |

### Transformation Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `zoom_scale` | float | 1.0 | Zoom per frame (>1.0 = zoom in, <1.0 = zoom out) |
| `pan_x` | int | 0 | Horizontal pan in pixels (+ = right, - = left) |
| `pan_y` | int | 0 | Vertical pan in pixels (+ = down, - = up) |
| `rotate_degrees` | float | 0.0 | Rotation per frame (+ = CW, - = CCW) |

### Loop-Only Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `epochs` | int | 3 | Refinement passes (2-5 recommended) |

---

## 💡 Examples

### Example 1: Static Image

```bash
modal run modal_simple.py \
  --prompt "cyberpunk city at sunset" \
  --iterations 1000 \
  --size 1024 1024
```

### Example 2: Rotating Video

```bash
curl -X POST "https://edenartlab--vqgan-clip-video-web.modal.run/jobs/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "ancient temple in mystical forest",
    "num_frames": 60,
    "rotate_degrees": 2.0,
    "width": 768,
    "height": 768,
    "fps": 30,
    "iterations_per_frame": 100
  }'
```

### Example 3: Zoom In Loop

```bash
curl -X POST "https://edenartlab--vqgan-clip-video-web.modal.run/jobs/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "fractal tunnel of infinite complexity",
    "num_frames": 120,
    "zoom_scale": 1.01,
    "epochs": 4,
    "width": 512,
    "height": 512,
    "fps": 30
  }'
```

### Example 4: Pan + Rotate Loop

```bash
curl -X POST "https://edenartlab--vqgan-clip-video-web.modal.run/jobs/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "steampunk godzilla in neon tokyo",
    "num_frames": 90,
    "rotate_degrees": 4.0,
    "pan_x": 3,
    "epochs": 3,
    "width": 512,
    "height": 512
  }'
```

---

## 🐍 Python Client Example

```python
import requests
import time

API_URL = "https://edenartlab--vqgan-clip-video-web.modal.run"

# Submit job
response = requests.post(f"{API_URL}/jobs/submit", json={
    "prompt": "mystical mandala rotating through space",
    "num_frames": 90,
    "rotate_degrees": 4.0,
    "epochs": 3,
    "width": 512,
    "height": 512,
})

job = response.json()
print(f"✓ Job submitted: {job['job_id']}")
print(f"  Output: {job['output_name']}")

# Poll for completion
while True:
    status = requests.get(f"{API_URL}/jobs/{job['job_id']}").json()

    if status['status'] == 'completed':
        print(f"\n✓ Job complete!")
        filename = status['result']['filename']
        break

    print(f"  Status: {status['status']} (checking again in 60s...)")
    time.sleep(60)

# Download video
print(f"\n⬇ Downloading {filename}...")
video = requests.get(f"{API_URL}/videos/{filename}")

with open(filename, "wb") as f:
    f.write(video.content)

print(f"✓ Saved to {filename}")
```

---

## 🔧 Local Development Tools

### Submit Job (CLI)

```bash
modal run modal_video.py::submit_loop_job \
  --prompt "test video" \
  --num-frames 30 \
  --epochs 2
```

### List Videos

```bash
modal run modal_video.py::list_videos_cli
```

### Download Video

```bash
modal run modal_video.py::download_video_cli --filename test_video.mp4
```

---

## ⚙️ API Endpoints Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API information |
| `POST` | `/jobs/submit` | Submit a new video generation job |
| `GET` | `/jobs/{job_id}` | Check job status |
| `GET` | `/videos` | List all videos in storage |
| `GET` | `/videos/{filename}` | Download a specific video |
| `DELETE` | `/videos/{filename}` | Delete a video from storage |

---

## 📊 Performance Guide

### Quality vs Speed Trade-offs

| Setting | Speed | Quality | Use Case |
|---------|-------|---------|----------|
| `iterations_per_frame: 25` | Fast | Low | Quick tests |
| `iterations_per_frame: 50` | Medium | Good | Production |
| `iterations_per_frame: 100` | Slow | High | Final renders |

### Resolution Guide

| Resolution | Description | GPU Usage |
|------------|-------------|-----------|
| 256×256 | Low (fast) | Light |
| 512×512 | Medium (recommended) | Moderate |
| 768×768 | High | Heavy |
| 1024×1024 | Very High | Very Heavy |

### Loop Epoch Guide

| Epochs | Quality | Time Multiplier |
|--------|---------|-----------------|
| 2 | Good loop | 2× |
| 3 | Better loop | 3× |
| 4 | Excellent loop | 4× |
| 5 | Perfect loop | 5× |

---

## ❓ FAQ

**Q: How long does a job take?**
- Simple video (30 frames): ~5-10 minutes
- Loop video (90 frames, 3 epochs): ~30-60 minutes
- High quality loop (120 frames, 5 epochs): ~2-4 hours

**Q: What happens if I lose internet during a job?**
- Jobs submitted via the API continue running in Modal's cloud
- You can check status and download results later

**Q: How do I make a perfect 360° rotation?**
- Use `rotate_degrees = 360 / num_frames`
- Set `epochs` to 3 or higher
- Example: 90 frames with 4° rotation = 360° total

**Q: Can I use custom init images?**
- Not currently supported via API, but can be added

**Q: How long are videos stored?**
- Videos persist in Modal storage indefinitely
- Delete them manually when no longer needed

**Q: Can I run multiple jobs simultaneously?**
- Yes! Each job runs independently

---

## 🎯 Pro Tips

1. **Perfect Loops**: Use `epochs: 3+` and ensure rotation/zoom values complete full cycles
2. **High Quality**: Increase `iterations_per_frame` to 100+ for final renders
3. **Fast Previews**: Use 256×256 resolution with 25 iterations_per_frame
4. **Smooth Motion**: More frames = smoother but slower (30-120 frames recommended)
5. **Disconnect-Proof**: Always use the API for long jobs, not `modal run`

---

## 📝 Notes

- All videos are saved to persistent Modal storage
- Jobs survive internet disconnections
- Generated videos are MP4 format
- Maximum timeout: 6 hours per job
- GPU: NVIDIA T4

---

## 🆘 Troubleshooting

**Job stuck in "running" state:**
- Check Modal dashboard: https://modal.com/apps
- View logs for the specific function call

**"generate.py not found" error:**
- Redeploy: `modal deploy modal_video.py`

**API returns 404:**
- Verify your deployment is active
- Check URL matches your Modal username

**Download fails:**
- Ensure job completed successfully
- Check video exists: `GET /videos`

---

## 📚 Additional Resources

- [Modal Documentation](https://modal.com/docs)
- [VQGAN-CLIP Paper](https://arxiv.org/abs/2104.14806)
- [Original VQGAN-CLIP README](./README.md)
