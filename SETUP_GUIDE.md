# VQGAN-CLIP Setup Guide for GPU Cloud Computing

This guide will help you run VQGAN-CLIP without a local GPU using cloud services.

## Table of Contents
- [Option 1: Modal (Recommended - Easiest)](#option-1-modal-recommended)
- [Option 2: Docker (For your own GPU server)](#option-2-docker)
- [Option 3: RunPod/Vast.ai](#option-3-runpodvastai)

---

## Option 1: Modal (Recommended)

Modal is a serverless platform that provides GPU access on-demand. You only pay for what you use.

### Setup Steps

1. **Install Modal**
   ```bash
   pip install modal
   ```

2. **Create a Modal account and authenticate**
   ```bash
   modal setup
   ```
   This will open a browser window to create an account or log in.

3. **Run VQGAN-CLIP on Modal**
   ```bash
   # Basic usage with default prompt
   modal run modal_simple.py

   # Custom prompt
   modal run modal_simple.py --prompt "A cyberpunk city at sunset"

   # Full options
   modal run modal_simple.py \
     --prompt "A surreal landscape with floating islands" \
     --iterations 500 \
     --width 512 \
     --height 512 \
     --output my_image.png \
     --seed 42
   ```

4. **First run will:**
   - Download models (~1.7GB) to a persistent Modal volume
   - Spin up a GPU instance (T4)
   - Generate your image
   - Download the result to your local machine

5. **Subsequent runs** will be faster as models are cached.

### Modal Pricing
- ~$0.0004 per second for T4 GPU
- A typical 500-iteration generation takes ~2-5 minutes
- Cost per image: roughly $0.05-$0.12
- Free trial credits available

### Advantages
- ✅ No Docker/containerization knowledge needed
- ✅ No local GPU required
- ✅ Automatic dependency management
- ✅ Pay only for compute time used
- ✅ Models persist between runs (fast subsequent runs)
- ✅ Run from command line on your Mac

---

## Option 2: Docker

Use this if you have access to a GPU server or cloud instance (AWS, GCP, Azure, etc.)

### Prerequisites
- Docker installed
- NVIDIA Container Toolkit (for GPU support)
- A machine with NVIDIA GPU

### Setup Steps

1. **Install NVIDIA Container Toolkit** (if not already installed)
   ```bash
   # Ubuntu/Debian
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
   sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
   sudo systemctl restart docker
   ```

2. **Build the Docker image**
   ```bash
   docker build -t vqgan-clip .
   ```
   This will take 10-20 minutes (downloads models during build).

3. **Run the container**
   ```bash
   # Create outputs directory
   mkdir -p outputs

   # Basic usage
   docker run --gpus all -v $(pwd)/outputs:/app/outputs vqgan-clip \
     -p "A painting of an apple in a fruit bowl" \
     -o outputs/output.png

   # With custom parameters
   docker run --gpus all -v $(pwd)/outputs:/app/outputs vqgan-clip \
     -p "A cyberpunk city at sunset" \
     -i 500 \
     -s 512 512 \
     -o outputs/cyberpunk.png
   ```

4. **Using docker-compose** (alternative)
   ```bash
   # Edit docker-compose.yml to change the prompt
   docker-compose up
   ```

### Advantages
- ✅ Reproducible environment
- ✅ Works on any cloud provider with NVIDIA GPUs
- ✅ No Python environment conflicts

### Disadvantages
- ❌ Requires GPU server access
- ❌ Need to manage server yourself
- ❌ Pay for full server time (even when not generating)

---

## Option 3: RunPod/Vast.ai

These are GPU rental platforms where you can run Docker containers.

### RunPod Setup

1. **Sign up at [RunPod.io](https://runpod.io)**

2. **Deploy a pod**
   - Choose a GPU (RTX 3090, RTX 4090, or A4000 recommended)
   - Select "RunPod Pytorch" template
   - Deploy pod

3. **Connect to your pod** (via SSH or Jupyter)

4. **Clone and run**
   ```bash
   git clone https://github.com/nerdyrodent/VQGAN-CLIP
   cd VQGAN-CLIP

   # Install dependencies
   pip install torch==1.9.0+cu111 torchvision==0.10.0+cu111 torchaudio==0.9.0 -f https://download.pytorch.org/whl/torch_stable.html
   pip install ftfy regex tqdm omegaconf pytorch-lightning IPython kornia imageio imageio-ffmpeg einops torch_optimizer setuptools==59.5.0

   # Clone dependencies
   git clone https://github.com/openai/CLIP
   git clone https://github.com/CompVis/taming-transformers

   # Download models
   mkdir checkpoints
   curl -L -o checkpoints/vqgan_imagenet_f16_16384.yaml -C - 'https://heibox.uni-heidelberg.de/d/a7530b09fed84f80a887/files/?p=%2Fconfigs%2Fmodel.yaml&dl=1'
   curl -L -o checkpoints/vqgan_imagenet_f16_16384.ckpt -C - 'https://heibox.uni-heidelberg.de/d/a7530b09fed84f80a887/files/?p=%2Fckpts%2Flast.ckpt&dl=1'

   # Generate!
   python generate.py -p "Your prompt here"
   ```

### Vast.ai Setup

Similar to RunPod, but generally cheaper:

1. **Sign up at [Vast.ai](https://vast.ai)**
2. **Search for instances** with NVIDIA GPUs
3. **Rent instance** with Pytorch template
4. **Follow same steps as RunPod**

### Pricing Comparison
- **RunPod**: $0.20-$0.60/hr depending on GPU
- **Vast.ai**: $0.10-$0.40/hr (spot pricing, can be interrupted)
- **Modal**: ~$0.05-$0.12 per image (pay per second)

---

## Recommended Approach for Your Use Case

Since you mentioned you don't have a local GPU and want command-line access, I **strongly recommend Modal**:

### Why Modal is Best for You:

1. **No GPU server management** - Just install Modal CLI and run
2. **Pay per use** - Only charged for generation time (~$0.05-0.12 per image)
3. **Fast iterations** - Models cached between runs
4. **Works from your Mac** - No need for cloud server setup
5. **Simple commands** - Just `modal run modal_app.py --prompt "..."`

### Quick Start (Modal):

```bash
# Install Modal
pip install modal

# Setup account (opens browser)
modal setup

# Generate an image!
modal run modal_simple.py --prompt "A surreal dreamscape with floating crystals"

# That's it! Image saved to output.png
```

---

## Common Parameters

For all methods, you can use these parameters:

- `-p`, `--prompt`: Text description (required)
- `-i`, `--iterations`: Number of iterations (default: 500)
  - More = better quality but slower
  - Try: 200 (draft), 500 (good), 1000 (high quality)
- `-s`, `--size`: Image size (default: 512x512)
  - Larger = more VRAM needed
  - Try: 380x380 (8GB VRAM), 512x512 (10GB), 900x900 (24GB)
- `-o`, `--output`: Output filename
- `-sd`, `--seed`: Random seed for reproducibility

### Example Prompts

```bash
# Simple scene
"A painting of a cat sitting on a windowsill"

# Multiple concepts with weights
"A forest landscape | magical | ethereal:0.7 | mystical:0.5"

# Style transfer
"A portrait in the style of Van Gogh | impressionist"

# Complex scene
"An astronaut riding a horse through a nebula | cinematic | 4k | detailed"
```

---

## Troubleshooting

### Modal Issues

**Error: "modal command not found"**
```bash
pip install --upgrade modal
```

**Error: "Not authenticated"**
```bash
modal setup
```

**Slow first run**
- First run downloads models (~1.7GB), subsequent runs are much faster

### Docker Issues

**Error: "could not select device driver"**
- Install NVIDIA Container Toolkit
- Check: `docker run --rm --gpus all nvidia/cuda:11.1.1-base nvidia-smi`

**Error: "CUDA out of memory"**
- Reduce image size: `-s 380 380` or `-s 256 256`

### General Issues

**Poor quality results**
- Increase iterations: `-i 1000` or `-i 1500`
- Adjust prompt (be more specific)
- Try different seeds

**Old Python/CUDA compatibility**
- This project is from 2021 and uses older versions
- Stick to the specified versions (PyTorch 1.9.0, CUDA 11.1)

---

## Next Steps

1. **Choose your platform** (I recommend Modal for ease of use)
2. **Try the basic example** to ensure everything works
3. **Experiment with prompts** and parameters
4. **Share your creations!**

Need help? The Modal option is the easiest to debug from your Mac.
