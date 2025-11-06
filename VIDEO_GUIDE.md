# VQGAN-CLIP Video Feedback Loop Guide

## Overview

The video feedback loop creates morphing, evolving videos where each frame uses the previous frame as an initialization image, creating smooth transitions and psychedelic effects.

## Quick Start

```bash
# Generate a short test video (5 frames, fast)
modal run modal_video.py \
  --prompt "Morphing psychedelic patterns" \
  --num-frames 5 \
  --iterations-per-frame 30 \
  --width 256 \
  --height 256 \
  --fps 2

# Generate a quality video (20 frames, better quality)
modal run modal_video.py \
  --prompt "A dreamscape morphing through surreal landscapes" \
  --num-frames 20 \
  --iterations-per-frame 50 \
  --width 512 \
  --height 512 \
  --fps 10 \
  --output my_video.mp4
```

## How It Works

1. **Frame 1**: Generated from the text prompt alone (random init)
2. **Frame 2**: Uses Frame 1 as init image (30% influence) + text prompt
3. **Frame 3**: Uses Frame 2 as init image (30% influence) + text prompt
4. **Frame N**: Uses Frame N-1 as init image (30% influence) + text prompt

This creates a **feedback loop** where each frame evolves from the previous one while still being guided by the text prompt.

## Parameters

### Basic Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--prompt` | Required | Text description guiding the video |
| `--num-frames` | 20 | Total number of frames to generate |
| `--iterations-per-frame` | 50 | Optimization iterations per frame |
| `--width` | 256 | Frame width in pixels |
| `--height` | 256 | Frame height in pixels |
| `--fps` | 10 | Frames per second in output video |
| `--seed` | Random | Random seed (only affects first frame) |
| `--output` | output_video.mp4 | Output video filename |

### Recommended Settings

#### Quick Test (2.5 seconds, 5 frames)
```bash
modal run modal_video.py \
  --prompt "Your prompt here" \
  --num-frames 5 \
  --iterations-per-frame 30 \
  --width 256 \
  --height 256 \
  --fps 2
```
**Time**: ~2-3 minutes | **Cost**: ~$0.01-0.02

#### Draft Quality (2 seconds, 20 frames)
```bash
modal run modal_video.py \
  --prompt "Your prompt here" \
  --num-frames 20 \
  --iterations-per-frame 30 \
  --width 256 \
  --height 256 \
  --fps 10
```
**Time**: ~6-8 minutes | **Cost**: ~$0.03-0.05

#### Good Quality (3 seconds, 30 frames)
```bash
modal run modal_video.py \
  --prompt "Your prompt here" \
  --num-frames 30 \
  --iterations-per-frame 50 \
  --width 512 \
  --height 512 \
  --fps 10
```
**Time**: ~15-20 minutes | **Cost**: ~$0.08-0.12

#### High Quality (5 seconds, 50 frames)
```bash
modal run modal_video.py \
  --prompt "Your prompt here" \
  --num-frames 50 \
  --iterations-per-frame 100 \
  --width 512 \
  --height 512 \
  --fps 10
```
**Time**: ~40-50 minutes | **Cost**: ~$0.20-0.30

## Example Prompts

### Abstract/Psychedelic
```bash
modal run modal_video.py \
  --prompt "Morphing fractal patterns | kaleidoscope | psychedelic colors" \
  --num-frames 30 --fps 15
```

### Landscape Evolution
```bash
modal run modal_video.py \
  --prompt "A mystical forest transforming through seasons | magical | ethereal" \
  --num-frames 40 --fps 10
```

### Abstract to Concrete
```bash
modal run modal_video.py \
  --prompt "Abstract shapes coalescing into a cosmic nebula | space art | detailed" \
  --num-frames 25 --fps 10
```

### Stylized Character
```bash
modal run modal_video.py \
  --prompt "A wizard materializing from swirling energy | fantasy art | dramatic lighting" \
  --num-frames 20 --fps 12
```

## Tips for Better Videos

### 1. Prompt Design
- **Use descriptive, evocative language**: "Swirling cosmic nebula" > "Space"
- **Add style modifiers**: "| digital art | vibrant colors | detailed"
- **Use weights** for emphasis: "psychedelic:1.5 | calm:0.3"

### 2. Frame Count vs FPS
- **More frames = smoother transitions** but longer generation time
- **Higher FPS = faster playback** but may look choppy if too few frames
- **Sweet spot**: 20-30 frames at 10 FPS = 2-3 second smooth videos

### 3. Iterations Per Frame
- **30 iterations**: Fast, lower quality, more abstract
- **50 iterations**: Good balance of speed and quality
- **100+ iterations**: High quality but slow, diminishing returns

### 4. Resolution Trade-offs
- **256x256**: Fast, good for tests
- **512x512**: Good quality, reasonable speed
- **768x768**: High quality but requires more VRAM and time

### 5. Init Weight (hardcoded to 0.3)
- Currently set to 0.3 (30% influence from previous frame)
- Lower = more change between frames (more chaotic)
- Higher = less change between frames (more stable)
- Can be modified in modal_video.py line 164

## Cost Estimates

Based on T4 GPU pricing (~$0.0004/second):

| Configuration | Frames | Iters/Frame | Est. Time | Est. Cost |
|--------------|--------|-------------|-----------|-----------|
| Quick Test | 5 | 30 | 2-3 min | $0.01-0.02 |
| Draft | 20 | 30 | 6-8 min | $0.03-0.05 |
| Good | 30 | 50 | 15-20 min | $0.08-0.12 |
| High Quality | 50 | 100 | 40-50 min | $0.20-0.30 |

## Troubleshooting

### Video is too fast/slow
Adjust `--fps` parameter. Higher FPS = faster playback.

### Frames don't change much
The init weight (0.3) might be too high. Edit `modal_video.py` line 164 to reduce it to 0.1-0.2.

### Frames change too drastically
The init weight (0.3) might be too low. Edit `modal_video.py` line 164 to increase it to 0.5-0.7.

### Poor quality frames
- Increase `--iterations-per-frame` to 100 or more
- Increase `--width` and `--height` to 512 or 768
- Use more descriptive prompts

### Generation is too slow
- Reduce `--num-frames` for shorter videos
- Reduce `--iterations-per-frame` to 30 or 20
- Reduce `--width` and `--height` to 256 or 384

### Out of memory errors
- Reduce `--width` and `--height` to 384 or 256
- This codebase uses old dependencies that work with T4 GPUs (16GB VRAM)

## Technical Details

### Feedback Loop Implementation
Each frame after the first is generated with:
- **Prompt**: Your text description
- **Init Image**: Previous frame as PNG
- **Init Weight**: 0.3 (30% influence)
- **Iterations**: Specified per-frame iterations

### Video Encoding
- **Codec**: H.264 (libx264)
- **Pixel Format**: yuv420p (universal compatibility)
- **CRF**: 18 (high quality)
- **Container**: MP4

### File Structure
- Frames generated in `/tmp/frame_XXXX.png` on Modal GPU
- Video assembled with ffmpeg
- Final video downloaded to local machine

## Advanced Usage

### Custom Init Weight
Edit `modal_video.py` line 164 to change init weight:
```python
cmd.extend(["-iw", "0.5"])  # 50% influence from previous frame
```

### Starting with a Custom Image
Modify `modal_video.py` to pass `init_image_bytes` parameter in main():
```python
# Read your init image
with open("my_image.png", "rb") as f:
    init_bytes = f.read()

frames = generate_video_frames.remote(
    ...,
    init_image_bytes=init_bytes,  # Start from this image
    ...
)
```

## Examples Gallery

### Tested Configurations

1. **Proof of Concept** (WORKING ✓)
   ```bash
   modal run modal_video.py \
     --prompt "Morphing psychedelic patterns" \
     --num-frames 5 \
     --iterations-per-frame 30 \
     --width 256 \
     --height 256 \
     --fps 2 \
     --output test_video.mp4
   ```
   Result: 47KB video, 2.5 seconds, morphing patterns

## Next Steps

- Start with the Quick Test configuration to verify it works
- Experiment with different prompts and parameters
- Try longer videos with more frames
- Adjust init weight for different effects
- Share your creations!

Enjoy creating morphing video art with VQGAN-CLIP! 🎨🎬
