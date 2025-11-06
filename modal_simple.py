"""
Simple VQGAN-CLIP on Modal - wraps the original generate.py
Run with: modal run modal_simple.py --prompt "your text prompt here"
"""

import modal
from pathlib import Path

# Create Modal app
app = modal.App("vqgan-clip-simple")

# Create a volume for model checkpoints (persists between runs)
volume = modal.Volume.from_name("vqgan-models", create_if_missing=True)

# Define the image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.9")
    .apt_install("git", "curl", "ffmpeg")
    .pip_install(
        "torch==1.9.0",
        "torchvision==0.10.0",
        "torchaudio==0.9.0",
        extra_index_url="https://download.pytorch.org/whl/cu111"
    )
    .pip_install(
        "ftfy",
        "regex",
        "tqdm",
        "omegaconf",
        "pytorch-lightning==1.3.7",
        "torchmetrics==0.3.2",
        "IPython",
        "kornia==0.5.4",
        "imageio",
        "imageio-ffmpeg",
        "einops",
        "torch-optimizer",
        "setuptools==59.5.0",
        "Pillow==8.2.0",
        "requests",
    )
    .run_commands(
        "git clone https://github.com/openai/CLIP /root/CLIP",
        "git clone https://github.com/CompVis/taming-transformers /root/taming-transformers",
    )
)


@app.function(
    image=image,
    gpu="T4",
    timeout=3600,
    volumes={"/checkpoints": volume},
)
def download_models():
    """Download VQGAN models if they don't exist"""
    import subprocess
    from pathlib import Path

    checkpoint_dir = Path("/checkpoints")
    checkpoint_dir.mkdir(exist_ok=True)

    yaml_file = checkpoint_dir / "vqgan_imagenet_f16_16384.yaml"
    ckpt_file = checkpoint_dir / "vqgan_imagenet_f16_16384.ckpt"

    if not yaml_file.exists():
        print("Downloading model config...")
        subprocess.run([
            "curl", "-L", "-o", str(yaml_file), "-C", "-",
            "https://heibox.uni-heidelberg.de/d/a7530b09fed84f80a887/files/?p=%2Fconfigs%2Fmodel.yaml&dl=1"
        ], check=True)

    if not ckpt_file.exists():
        print("Downloading model checkpoint (this is ~1.7GB, may take a while)...")
        subprocess.run([
            "curl", "-L", "-o", str(ckpt_file), "-C", "-",
            "https://heibox.uni-heidelberg.de/d/a7530b09fed84f80a887/files/?p=%2Fckpts%2Flast.ckpt&dl=1"
        ], check=True)

    volume.commit()
    print("Models ready!")


@app.function(
    image=image,
    gpu="T4",
    timeout=3600,
    volumes={"/checkpoints": volume},
)
def generate_image(
    prompt: str,
    iterations: int = 500,
    image_size: tuple = (512, 512),
    seed: int = None,
    generate_py_code: str = None,
):
    """Generate an image from a text prompt using VQGAN-CLIP"""
    import subprocess
    import sys
    import os
    from pathlib import Path

    # Write generate.py to the container
    if generate_py_code:
        Path("/tmp/generate.py").write_text(generate_py_code)

    # Build command with environment variables to include CLIP and taming-transformers in path
    env = os.environ.copy()
    pythonpath = "/clip:/taming-transformers"
    if "PYTHONPATH" in env:
        pythonpath = f"{pythonpath}:{env['PYTHONPATH']}"
    env["PYTHONPATH"] = pythonpath

    cmd = [
        sys.executable, "/tmp/generate.py",
        "-p", prompt,
        "-i", str(iterations),
        "-s", str(image_size[0]), str(image_size[1]),
        "-conf", "/checkpoints/vqgan_imagenet_f16_16384.yaml",
        "-ckpt", "/checkpoints/vqgan_imagenet_f16_16384.ckpt",
        "-o", "/tmp/output.png"
    ]

    if seed is not None:
        cmd.extend(["-sd", str(seed)])

    print(f"Running: {' '.join(cmd)}")

    # Run the original generate.py with updated environment
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    if result.returncode != 0:
        raise RuntimeError(f"generate.py failed with code {result.returncode}")

    # Read the generated image
    output_path = Path("/tmp/output.png")
    if not output_path.exists():
        raise RuntimeError("Output image was not created")

    return output_path.read_bytes()


@app.local_entrypoint()
def main(
    prompt: str = "A painting of an apple in a fruit bowl",
    iterations: int = 500,
    width: int = 512,
    height: int = 512,
    seed: int = None,
    output: str = "output.png",
    video: bool = False,
):
    """
    Generate an image using VQGAN-CLIP

    Args:
        prompt: Text prompt describing the image
        iterations: Number of optimization iterations
        width: Image width
        height: Image height
        seed: Random seed (optional)
        output: Output filename
        video: Use modal_video.py for video generation instead
    """
    from pathlib import Path

    if video:
        print("\n" + "="*60)
        print("VIDEO MODE: Please use modal_video.py instead")
        print("="*60)
        print("Example:")
        print("  modal run modal_video.py \\")
        print(f"    --prompt \"{prompt}\" \\")
        print("    --num-frames 20 \\")
        print("    --iterations-per-frame 50 \\")
        print(f"    --width {width} \\")
        print(f"    --height {height} \\")
        print("    --fps 10 \\")
        print(f"    --output {output.replace('.png', '.mp4')}")
        print("="*60 + "\n")
        return

    # Read generate.py from local filesystem
    generate_py_path = Path("generate.py")
    if not generate_py_path.exists():
        raise RuntimeError("generate.py not found in current directory")

    generate_py_code = generate_py_path.read_text()

    # First, ensure models are downloaded
    print("Ensuring models are downloaded...")
    download_models.remote()

    # Generate the image
    print(f"\nGenerating image...")
    img_bytes = generate_image.remote(
        prompt=prompt,
        iterations=iterations,
        image_size=(width, height),
        seed=seed,
        generate_py_code=generate_py_code,
    )

    # Save locally
    output_path = Path(output)
    output_path.write_bytes(img_bytes)
    print(f"\nImage saved to: {output_path.absolute()}")
