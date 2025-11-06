# VQGAN-CLIP Quick Start with Modal

## TL;DR

```bash
# Install Modal
pip install modal

# Authenticate (opens browser)
modal setup

# Generate an image!
modal run modal_simple.py --prompt "A cyberpunk city at sunset"
```

The image will be saved to `output.png` in your current directory.

## What is Modal?

Modal is a serverless platform that lets you run code with GPUs in the cloud without managing servers. Perfect for this 2021 ML project that needs old dependencies and a GPU.

## How It Works

1. **You run the command** on your Mac (no GPU needed locally)
2. **Modal spins up a cloud GPU** (T4, costs ~$0.0004/sec)
3. **Generates your image** in the cloud
4. **Downloads it to your local machine** automatically
5. **GPU shuts down** (you only pay for generation time)

## Usage Examples

### Basic Generation
```bash
modal run modal_simple.py --prompt "A surreal dreamscape"
```

### Custom Size & Iterations
```bash
modal run modal_simple.py \
  --prompt "An astronaut riding a horse through a nebula" \
  --iterations 500 \
  --width 512 \
  --height 512 \
  --output my_masterpiece.png
```

### High Quality (More Iterations)
```bash
modal run modal_simple.py \
  --prompt "A magical forest with bioluminescent plants" \
  --iterations 1000
```

### Quick Draft (Fewer Iterations)
```bash
modal run modal_simple.py \
  --prompt "Test prompt" \
  --iterations 200
```

### Reproducible Results (Set Seed)
```bash
modal run modal_simple.py \
  --prompt "A painting of mountains" \
  --seed 42
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--prompt` | Required | Text description of the image |
| `--iterations` | 500 | More = better quality, but slower |
| `--width` | 512 | Image width in pixels |
| `--height` | 512 | Image height in pixels |
| `--output` | output.png | Where to save the image locally |
| `--seed` | Random | Set for reproducible results |

## Cost Estimate

- **T4 GPU**: ~$0.0004 per second
- **Typical run (500 iterations)**: 2-5 minutes
- **Cost per image**: $0.05 - $0.12

First time is slower (downloads ~1.7GB model), then it's cached!

## Advanced Prompting

### Multiple Concepts with Weights
```bash
modal run modal_simple.py \
  --prompt "A forest landscape | magical | mystical:0.7 | ethereal:0.5"
```

Weights control how much each concept influences the image.

### Style Transfer
```bash
modal run modal_simple.py \
  --prompt "A painting in the style of Van Gogh | impressionist"
```

## Troubleshooting

### "modal command not found"
```bash
pip install --upgrade modal
```

### "Not authenticated"
```bash
modal setup
```

### Image quality is poor
- Increase `--iterations` to 1000 or 1500
- Try being more specific in your prompt
- Experiment with different seeds

### It's slow
- First run downloads models (~1.7GB), subsequent runs are faster
- Consider reducing `--iterations` for faster results
- Default 500 iterations is a good balance

## Tips for Better Results

1. **Be specific**: "A cyberpunk city at sunset with neon lights" > "A city"
2. **Use artistic styles**: Add "digital art", "oil painting", "photograph", etc.
3. **Iterate**: Try different prompts and seeds
4. **Start with fewer iterations** (200) to test prompts quickly
5. **Use weights** to emphasize important concepts

## Example Prompts

```bash
# Landscape
modal run modal_simple.py --prompt "A mystical forest with glowing mushrooms | fantasy art | detailed"

# Abstract
modal run modal_simple.py --prompt "Swirling colors representing joy | abstract expressionism"

# Character
modal run modal_simple.py --prompt "A wise wizard with a long beard | fantasy illustration | detailed face"

# Sci-Fi
modal run modal_simple.py --prompt "A spaceship cockpit | sci-fi | cinematic lighting | detailed"

# Architecture
modal run modal_simple.py --prompt "A futuristic building | architectural visualization | glass and steel"
```

## Where Are My Images?

Images are saved in your current directory by default. You can specify a different location:

```bash
modal run modal_simple.py --prompt "Test" --output ~/Pictures/my_art.png
```

## Next Steps

- Read `SETUP_GUIDE.md` for alternative deployment options (Docker, RunPod, etc.)
- Experiment with different prompts and parameters
- Check Modal dashboard at https://modal.com to see your runs and costs

## Support

- Modal issues: Run `modal help` or visit https://modal.com/docs
- VQGAN-CLIP issues: See original README.md
- For bugs with the Modal integration: Check modal_simple.py

Enjoy creating art with VQGAN-CLIP! 🎨
