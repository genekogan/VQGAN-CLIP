"""
VQGAN-CLIP Video Feedback Loop on Modal
Creates a video where each frame is generated using the previous frame as init image
Run with: modal run modal_video.py --prompt "your text prompt here"
"""

import modal
from pathlib import Path

# Create Modal app
app = modal.App("vqgan-clip-video")

# Create volumes for persistence
models_volume = modal.Volume.from_name("vqgan-models", create_if_missing=True)
outputs_volume = modal.Volume.from_name("vqgan-outputs", create_if_missing=True)

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
    .add_local_file("generate.py", "/root/generate.py", copy=True)
    .run_commands(
        "git clone https://github.com/openai/CLIP /clip",
        "git clone https://github.com/CompVis/taming-transformers /taming-transformers",
    )
)


@app.function(
    image=image,
    gpu="T4",
    timeout=3600,
    volumes={"/checkpoints": models_volume},
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

    models_volume.commit()
    print("Models ready!")


@app.function(
    image=image,
    gpu="T4",
    timeout=21600,  # 6 hours for video generation
    volumes={"/checkpoints": models_volume},
)
def generate_video_frames(
    prompt: str,
    num_frames: int = 20,
    iterations_per_frame: int = 50,
    image_size: tuple = (256, 256),
    seed: int = None,
    init_image_bytes: bytes = None,
    generate_py_code: str = None,
    zoom_scale: float = 1.0,
    pan_x: int = 0,
    pan_y: int = 0,
    rotate_degrees: float = 0.0,
):
    """Generate video frames with feedback loop and optional transformations"""
    import subprocess
    import sys
    import os
    from pathlib import Path
    from PIL import Image, ImageChops
    import io

    # Write generate.py to the container with path fixes
    if generate_py_code:
        # Fix the paths in generate.py
        modified_code = generate_py_code.replace(
            "sys.path.append('taming-transformers')",
            "sys.path.append('/taming-transformers')\nsys.path.append('/clip')"
        )
        # Also fix CLIP import paths
        modified_code = modified_code.replace(
            "from CLIP import clip",
            "import clip"
        )
        Path("/tmp/generate.py").write_text(modified_code)

    # Build environment with CLIP and taming-transformers in path
    env = os.environ.copy()
    pythonpath = "/clip:/taming-transformers"
    if "PYTHONPATH" in env:
        pythonpath = f"{pythonpath}:{env['PYTHONPATH']}"
    env["PYTHONPATH"] = pythonpath

    frames = []

    for frame_idx in range(num_frames):
        print(f"\n{'='*60}")
        print(f"Generating frame {frame_idx + 1}/{num_frames}")
        print(f"{'='*60}")

        output_path = f"/tmp/frame_{frame_idx:04d}.png"

        # Build command
        cmd = [
            sys.executable, "/tmp/generate.py",
            "-p", prompt,
            "-i", str(iterations_per_frame),
            "-s", str(image_size[0]), str(image_size[1]),
            "-conf", "/checkpoints/vqgan_imagenet_f16_16384.yaml",
            "-ckpt", "/checkpoints/vqgan_imagenet_f16_16384.ckpt",
            "-o", output_path
        ]

        # Add seed for first frame only
        if seed is not None and frame_idx == 0:
            cmd.extend(["-sd", str(seed)])

        # Add init image if this is not the first frame
        if frame_idx > 0:
            # Load previous frame and apply transformations
            prev_frame = Image.open(io.BytesIO(frames[-1]))

            # Apply transformations if specified
            if zoom_scale != 1.0 or pan_x != 0 or pan_y != 0 or rotate_degrees != 0.0:
                # Apply rotation first
                if rotate_degrees != 0.0:
                    prev_frame = prev_frame.rotate(rotate_degrees, resample=Image.BICUBIC, expand=False)

                # Apply zoom
                if zoom_scale != 1.0:
                    w, h = prev_frame.size
                    # Zoom by cropping from center and resizing
                    zoom_factor = 1.0 / zoom_scale
                    new_w = int(w * zoom_factor)
                    new_h = int(h * zoom_factor)
                    left = (w - new_w) // 2
                    top = (h - new_h) // 2
                    prev_frame = prev_frame.crop((left, top, left + new_w, top + new_h))
                    prev_frame = prev_frame.resize((w, h), Image.LANCZOS)

                # Apply pan (shift)
                if pan_x != 0 or pan_y != 0:
                    prev_frame = ImageChops.offset(prev_frame, pan_x, pan_y)

            # Write transformed frame as init image
            init_path = f"/tmp/init_frame_{frame_idx:04d}.png"
            prev_frame.save(init_path)
            cmd.extend(["-ii", init_path])
            # Use init weight to blend with previous frame
            cmd.extend(["-iw", "0.3"])  # 30% influence from init image
        elif init_image_bytes:
            # Use provided init image for first frame
            init_path = "/tmp/init_frame_0000.png"
            Path(init_path).write_bytes(init_image_bytes)
            cmd.extend(["-ii", init_path])
            cmd.extend(["-iw", "0.3"])

        print(f"Running: {' '.join(cmd)}")

        # Run the original generate.py with updated environment
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)

        if result.returncode != 0:
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            raise RuntimeError(f"Frame {frame_idx} generation failed with code {result.returncode}")

        # Read the generated frame
        frame_path = Path(output_path)
        if not frame_path.exists():
            raise RuntimeError(f"Frame {frame_idx} was not created")

        frame_bytes = frame_path.read_bytes()
        frames.append(frame_bytes)

        # Show progress
        if frame_idx % 5 == 0 or frame_idx == num_frames - 1:
            print(f"Progress: {frame_idx + 1}/{num_frames} frames completed")

    print(f"\n{'='*60}")
    print(f"All {num_frames} frames generated successfully!")
    print(f"{'='*60}\n")

    return frames


@app.function(
    image=image,
    gpu="T4",
    timeout=21600,  # 6 hours for loop generation (epochs take much longer)
    volumes={"/checkpoints": models_volume},
)
def generate_loop_frames(
    prompt: str,
    num_frames: int = 90,
    iterations_per_frame: int = 50,
    image_size: tuple = (256, 256),
    seed: int = None,
    generate_py_code: str = None,
    zoom_scale: float = 1.0,
    pan_x: int = 0,
    pan_y: int = 0,
    rotate_degrees: float = 0.0,
    epochs: int = 3,
):
    """Generate perfect loop video frames with epoch-based interpolation refinement"""
    import subprocess
    import sys
    import os
    from pathlib import Path
    from PIL import Image, ImageChops
    import io
    import torch
    import torch.nn.functional as F
    from torchvision.transforms import functional as TF

    # Write generate.py to the container with path fixes
    if generate_py_code:
        modified_code = generate_py_code.replace(
            "sys.path.append('taming-transformers')",
            "sys.path.append('/taming-transformers')\nsys.path.append('/clip')"
        )
        modified_code = modified_code.replace(
            "from CLIP import clip",
            "import clip"
        )
        Path("/tmp/generate.py").write_text(modified_code)

    # Build environment with CLIP and taming-transformers in path
    env = os.environ.copy()
    pythonpath = "/clip:/taming-transformers"
    if "PYTHONPATH" in env:
        pythonpath = f"{pythonpath}:{env['PYTHONPATH']}"
    env["PYTHONPATH"] = pythonpath

    # Load VQGAN model for encoding frames
    sys.path.append('/taming-transformers')
    sys.path.append('/clip')
    from omegaconf import OmegaConf
    from taming.models import vqgan

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    config = OmegaConf.load("/checkpoints/vqgan_imagenet_f16_16384.yaml")
    model = vqgan.VQModel(**config.model.params)
    model.eval().requires_grad_(False)
    model.init_from_ckpt("/checkpoints/vqgan_imagenet_f16_16384.ckpt")
    model = model.to(device)
    del model.loss

    frames = []

    # Epoch 0: Generate initial sequence
    print(f"\n{'='*60}")
    print(f"EPOCH 0: Generating initial {num_frames} frames")
    print(f"{'='*60}\n")

    for frame_idx in range(num_frames):
        print(f"Frame {frame_idx + 1}/{num_frames}")

        output_path = f"/tmp/loop_frame_{frame_idx:04d}.png"

        # Build command
        cmd = [
            sys.executable, "/tmp/generate.py",
            "-p", prompt,
            "-i", str(iterations_per_frame),
            "-s", str(image_size[0]), str(image_size[1]),
            "-conf", "/checkpoints/vqgan_imagenet_f16_16384.yaml",
            "-ckpt", "/checkpoints/vqgan_imagenet_f16_16384.ckpt",
            "-o", output_path
        ]

        # Add seed for first frame only
        if seed is not None and frame_idx == 0:
            cmd.extend(["-sd", str(seed)])

        # Add init image if not first frame
        if frame_idx > 0:
            # Load previous frame and apply transformations
            prev_frame = Image.open(io.BytesIO(frames[-1]))
            prev_frame = apply_transformations(prev_frame, zoom_scale, pan_x, pan_y, rotate_degrees)

            # Write transformed frame as init image
            init_path = f"/tmp/loop_init_{frame_idx:04d}.png"
            prev_frame.save(init_path)
            cmd.extend(["-ii", init_path, "-iw", "0.3"])

        # Run generation
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            raise RuntimeError(f"Frame {frame_idx} generation failed")

        # Read and store frame
        frame_bytes = Path(output_path).read_bytes()
        frames.append(frame_bytes)

        if (frame_idx + 1) % 10 == 0:
            print(f"Progress: {frame_idx + 1}/{num_frames} frames")

    # Refinement epochs: Loop back and interpolate
    for epoch in range(1, epochs):
        print(f"\n{'='*60}")
        print(f"EPOCH {epoch}: Refining frames with interpolation")
        print(f"{'='*60}\n")

        for frame_idx in range(num_frames):
            # Calculate interpolation weight
            # Progress through this epoch determines blend between prev and next frame
            total_progress = (epoch - 1) / (epochs - 1)  # Overall progress through all epochs
            frame_progress = frame_idx / num_frames  # Progress through current loop
            combined_progress = (total_progress + frame_progress / epochs)

            # Weight: starts at 1.0 (all previous) and moves toward 0.0 (all next)
            prev_weight = 1.0 - combined_progress
            next_weight = combined_progress

            print(f"Frame {frame_idx + 1}/{num_frames} (prev: {prev_weight:.3f}, next: {next_weight:.3f})")

            output_path = f"/tmp/loop_frame_{frame_idx:04d}.png"

            # Get previous and next frame indices (with wrapping)
            prev_idx = (frame_idx - 1) % num_frames
            next_idx = (frame_idx + 1) % num_frames

            # Load and transform previous frame
            prev_frame = Image.open(io.BytesIO(frames[prev_idx]))
            prev_frame = apply_transformations(prev_frame, zoom_scale, pan_x, pan_y, rotate_degrees)

            # Load next frame (no transformation needed, it's the target)
            next_frame = Image.open(io.BytesIO(frames[next_idx]))

            # Encode both frames to latent space
            prev_tensor = TF.to_tensor(prev_frame).unsqueeze(0).to(device) * 2 - 1
            next_tensor = TF.to_tensor(next_frame).unsqueeze(0).to(device) * 2 - 1

            with torch.inference_mode():
                prev_z, *_ = model.encode(prev_tensor)
                next_z, *_ = model.encode(next_tensor)

            # Interpolate in latent space
            interpolated_z = prev_weight * prev_z + next_weight * next_z

            # Decode interpolated latent back to image
            with torch.inference_mode():
                interpolated_img = model.decode(interpolated_z).add(1).div(2).clamp(0, 1)
                interpolated_pil = TF.to_pil_image(interpolated_img[0].cpu())

            # Save interpolated image as init
            init_path = f"/tmp/loop_init_{frame_idx:04d}.png"
            interpolated_pil.save(init_path)

            # Build command with interpolated init image
            cmd = [
                sys.executable, "/tmp/generate.py",
                "-p", prompt,
                "-i", str(iterations_per_frame),
                "-s", str(image_size[0]), str(image_size[1]),
                "-conf", "/checkpoints/vqgan_imagenet_f16_16384.yaml",
                "-ckpt", "/checkpoints/vqgan_imagenet_f16_16384.ckpt",
                "-o", output_path,
                "-ii", init_path,
                "-iw", "0.3"
            ]

            # Run generation
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            if result.returncode != 0:
                raise RuntimeError(f"Epoch {epoch}, Frame {frame_idx} generation failed")

            # Update frame in list
            frames[frame_idx] = Path(output_path).read_bytes()

            if (frame_idx + 1) % 10 == 0:
                print(f"Progress: {frame_idx + 1}/{num_frames} frames")

    print(f"\n{'='*60}")
    print(f"Perfect loop generation complete!")
    print(f"Total frames: {num_frames}, Epochs: {epochs}")
    print(f"{'='*60}\n")

    return frames


def apply_transformations(img: "Image.Image", zoom_scale: float, pan_x: int, pan_y: int, rotate_degrees: float) -> "Image.Image":
    """Apply transformations to an image"""
    from PIL import Image, ImageChops

    if zoom_scale == 1.0 and pan_x == 0 and pan_y == 0 and rotate_degrees == 0.0:
        return img

    # Apply rotation first
    if rotate_degrees != 0.0:
        img = img.rotate(rotate_degrees, resample=Image.BICUBIC, expand=False)

    # Apply zoom
    if zoom_scale != 1.0:
        w, h = img.size
        zoom_factor = 1.0 / zoom_scale
        new_w = int(w * zoom_factor)
        new_h = int(h * zoom_factor)
        left = (w - new_w) // 2
        top = (h - new_h) // 2
        img = img.crop((left, top, left + new_w, top + new_h))
        img = img.resize((w, h), Image.LANCZOS)

    # Apply pan (shift)
    if pan_x != 0 or pan_y != 0:
        img = ImageChops.offset(img, pan_x, pan_y)

    return img


@app.function(
    image=image,
    gpu="T4",
    timeout=21600,  # 6 hours for video creation
    volumes={"/checkpoints": models_volume},
)
def create_video_from_frames(frames_bytes: list, fps: int = 10, output_format: str = "mp4"):
    """Create video from frame bytes"""
    import subprocess
    from pathlib import Path
    import imageio

    # Write frames to disk
    frame_dir = Path("/tmp/video_frames")
    frame_dir.mkdir(exist_ok=True)

    print(f"Writing {len(frames_bytes)} frames to disk...")
    for idx, frame_bytes in enumerate(frames_bytes):
        frame_path = frame_dir / f"frame_{idx:04d}.png"
        frame_path.write_bytes(frame_bytes)

    # Create video using ffmpeg
    output_path = f"/tmp/output.{output_format}"

    print(f"Creating {output_format} video at {fps} FPS...")

    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(frame_dir / "frame_%04d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",  # High quality
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("FFMPEG STDERR:", result.stderr)
        raise RuntimeError(f"Video creation failed with code {result.returncode}")

    print(f"Video created successfully!")

    # Read video file
    video_bytes = Path(output_path).read_bytes()

    return video_bytes


@app.local_entrypoint()
def main(
    prompt: str = "A psychedelic dreamscape morphing and evolving",
    num_frames: int = 20,
    iterations_per_frame: int = 50,
    width: int = 256,
    height: int = 256,
    fps: int = 10,
    seed: int = None,
    output: str = "output_video.mp4",
    zoom_scale: float = 1.0,
    pan_x: int = 0,
    pan_y: int = 0,
    rotate_degrees: float = 0.0,
):
    """
    Generate a feedback loop video using VQGAN-CLIP with optional transformations

    Args:
        prompt: Text prompt describing the video theme
        num_frames: Number of frames to generate
        iterations_per_frame: Optimization iterations per frame (lower = faster but lower quality)
        width: Frame width
        height: Frame height
        fps: Frames per second for output video
        seed: Random seed (optional, only affects first frame)
        output: Output video filename
        zoom_scale: Zoom scale per frame (1.0 = no zoom, <1.0 = zoom out, >1.0 = zoom in)
        pan_x: Horizontal pan in pixels per frame (negative = left, positive = right)
        pan_y: Vertical pan in pixels per frame (negative = up, positive = down)
        rotate_degrees: Rotation in degrees per frame (negative = CCW, positive = CW)
    """
    from pathlib import Path

    print(f"\n{'='*60}")
    print(f"VQGAN-CLIP Video Feedback Loop")
    print(f"{'='*60}")
    print(f"Prompt: {prompt}")
    print(f"Frames: {num_frames}")
    print(f"Iterations per frame: {iterations_per_frame}")
    print(f"Resolution: {width}x{height}")
    print(f"FPS: {fps}")
    if zoom_scale != 1.0:
        print(f"Zoom scale: {zoom_scale} ({'zoom in' if zoom_scale > 1.0 else 'zoom out'})")
    if pan_x != 0:
        print(f"Pan X: {pan_x}px ({'right' if pan_x > 0 else 'left'})")
    if pan_y != 0:
        print(f"Pan Y: {pan_y}px ({'down' if pan_y > 0 else 'up'})")
    if rotate_degrees != 0.0:
        print(f"Rotate: {rotate_degrees}° ({'CW' if rotate_degrees > 0 else 'CCW'})")
    print(f"{'='*60}\n")

    # Read generate.py from local filesystem
    generate_py_path = Path("generate.py")
    if not generate_py_path.exists():
        raise RuntimeError("generate.py not found in current directory")

    generate_py_code = generate_py_path.read_text()

    # First, ensure models are downloaded
    print("Ensuring models are downloaded...")
    download_models.remote()

    # Generate video frames
    print(f"\nGenerating {num_frames} frames with feedback loop...")
    frames = generate_video_frames.remote(
        prompt=prompt,
        num_frames=num_frames,
        iterations_per_frame=iterations_per_frame,
        image_size=(width, height),
        seed=seed,
        init_image_bytes=None,
        generate_py_code=generate_py_code,
        zoom_scale=zoom_scale,
        pan_x=pan_x,
        pan_y=pan_y,
        rotate_degrees=rotate_degrees,
    )

    # Create video from frames
    print(f"\nCreating video from {len(frames)} frames...")
    video_bytes = create_video_from_frames.remote(
        frames_bytes=frames,
        fps=fps,
    )

    # Save video locally
    output_path = Path(output)
    output_path.write_bytes(video_bytes)

    print(f"\n{'='*60}")
    print(f"Video saved to: {output_path.absolute()}")
    print(f"Duration: {num_frames / fps:.1f} seconds")
    print(f"Total frames: {num_frames}")
    print(f"{'='*60}\n")


@app.local_entrypoint()
def main_loop(
    prompt: str = "A psychedelic dreamscape rotating through infinite space",
    num_frames: int = 90,
    iterations_per_frame: int = 50,
    width: int = 256,
    height: int = 256,
    fps: int = 30,
    seed: int = None,
    output: str = "output_loop.mp4",
    zoom_scale: float = 1.0,
    pan_x: int = 0,
    pan_y: int = 0,
    rotate_degrees: float = 4.0,
    epochs: int = 3,
):
    """
    Generate a perfect looping video using VQGAN-CLIP with epoch-based interpolation refinement

    This creates videos where the last frame seamlessly transitions back to the first frame,
    creating an infinite loop. The algorithm works by:
    1. Generating an initial sequence of frames with transformations
    2. Refining frames over multiple epochs by interpolating between the transformed previous
       frame and the existing next frame in latent space
    3. Gradually shifting weight from previous to next frame across epochs

    Args:
        prompt: Text prompt describing the video theme
        num_frames: Number of frames in the loop (more = smoother but longer generation)
        iterations_per_frame: Optimization iterations per frame (lower = faster but lower quality)
        width: Frame width
        height: Frame height
        fps: Frames per second for output video
        seed: Random seed (optional, only affects first frame)
        output: Output video filename
        zoom_scale: Zoom scale per frame (1.0 = no zoom, <1.0 = zoom out, >1.0 = zoom in)
        pan_x: Horizontal pan in pixels per frame (negative = left, positive = right)
        pan_y: Vertical pan in pixels per frame (negative = up, positive = down)
        rotate_degrees: Rotation in degrees per frame (360/num_frames for full rotation)
        epochs: Number of refinement passes (2-5 recommended, more = smoother loop)

    Example for 360° rotation loop over 90 frames:
        modal run modal_video.py::main_loop \\
            --prompt "A mystical mandala in deep space" \\
            --num-frames 90 \\
            --rotate-degrees 4.0 \\
            --epochs 3
    """
    from pathlib import Path

    print(f"\n{'='*60}")
    print(f"VQGAN-CLIP Perfect Loop Generator")
    print(f"{'='*60}")
    print(f"Prompt: {prompt}")
    print(f"Frames: {num_frames}")
    print(f"Epochs: {epochs}")
    print(f"Iterations per frame: {iterations_per_frame}")
    print(f"Resolution: {width}x{height}")
    print(f"FPS: {fps}")
    if zoom_scale != 1.0:
        print(f"Zoom scale: {zoom_scale} ({'zoom in' if zoom_scale > 1.0 else 'zoom out'})")
    if pan_x != 0:
        print(f"Pan X: {pan_x}px ({'right' if pan_x > 0 else 'left'})")
    if pan_y != 0:
        print(f"Pan Y: {pan_y}px ({'down' if pan_y > 0 else 'up'})")
    if rotate_degrees != 0.0:
        print(f"Rotate: {rotate_degrees}° per frame ({'CW' if rotate_degrees > 0 else 'CCW'})")
        total_rotation = rotate_degrees * num_frames
        print(f"  → Total rotation: {total_rotation}°")
    print(f"{'='*60}\n")

    # Read generate.py from local filesystem
    generate_py_path = Path("generate.py")
    if not generate_py_path.exists():
        raise RuntimeError("generate.py not found in current directory")

    generate_py_code = generate_py_path.read_text()

    # First, ensure models are downloaded
    print("Ensuring models are downloaded...")
    download_models.remote()

    # Generate perfect loop frames
    print(f"\nGenerating perfect loop with {num_frames} frames over {epochs} epochs...")
    frames = generate_loop_frames.remote(
        prompt=prompt,
        num_frames=num_frames,
        iterations_per_frame=iterations_per_frame,
        image_size=(width, height),
        seed=seed,
        generate_py_code=generate_py_code,
        zoom_scale=zoom_scale,
        pan_x=pan_x,
        pan_y=pan_y,
        rotate_degrees=rotate_degrees,
        epochs=epochs,
    )

    # Create video from frames
    print(f"\nCreating looping video from {len(frames)} frames...")
    video_bytes = create_video_from_frames.remote(
        frames_bytes=frames,
        fps=fps,
    )

    # Save video locally
    output_path = Path(output)
    output_path.write_bytes(video_bytes)

    print(f"\n{'='*60}")
    print(f"Perfect loop saved to: {output_path.absolute()}")
    print(f"Duration: {num_frames / fps:.1f} seconds")
    print(f"Total frames: {num_frames}")
    print(f"Epochs processed: {epochs}")
    print(f"{'='*60}\n")
    print("Tip: Set your video player to loop mode to see the seamless transition!")


# ============================================================================
# Background Job Functions (called by web API)
# ============================================================================

@app.function(
    image=image,
    gpu="T4",
    timeout=21600,
    volumes={
        "/checkpoints": models_volume,
        "/outputs": outputs_volume,
    },
)
def generate_and_save_loop(
    prompt: str,
    output_name: str,
    generate_py_code: str,  # Now passed as parameter
    num_frames: int = 90,
    iterations_per_frame: int = 50,
    width: int = 256,
    height: int = 256,
    fps: int = 30,
    seed: int = None,
    zoom_scale: float = 1.0,
    pan_x: int = 0,
    pan_y: int = 0,
    rotate_degrees: float = 4.0,
    epochs: int = 3,
):
    """Generate loop and save to Modal volume (for remote jobs)"""
    from pathlib import Path
    import sys

    print(f"Starting remote job: {output_name}")

    # Ensure models are downloaded
    download_models.local()

    # Generate frames
    frames = generate_loop_frames.local(
        prompt=prompt,
        num_frames=num_frames,
        iterations_per_frame=iterations_per_frame,
        image_size=(width, height),
        seed=seed,
        generate_py_code=generate_py_code,
        zoom_scale=zoom_scale,
        pan_x=pan_x,
        pan_y=pan_y,
        rotate_degrees=rotate_degrees,
        epochs=epochs,
    )

    # Create video
    video_bytes = create_video_from_frames.local(
        frames_bytes=frames,
        fps=fps,
    )

    # Save to volume
    output_path = Path("/outputs") / output_name
    output_path.write_bytes(video_bytes)
    outputs_volume.commit()

    print(f"✓ Saved to Modal volume: {output_name}")
    return {"status": "success", "filename": output_name, "size_mb": len(video_bytes) / 1024 / 1024}


@app.function(
    volumes={"/outputs": outputs_volume},
    timeout=600,
)
def list_videos():
    """List all videos in the outputs volume"""
    from pathlib import Path

    outputs_dir = Path("/outputs")
    if not outputs_dir.exists():
        return []

    videos = []
    for video_file in outputs_dir.glob("*.mp4"):
        stat = video_file.stat()
        videos.append({
            "filename": video_file.name,
            "size_mb": stat.st_size / 1024 / 1024,
            "modified": stat.st_mtime,
        })

    return sorted(videos, key=lambda x: x["modified"], reverse=True)


@app.function(
    volumes={"/outputs": outputs_volume},
    timeout=600,
)
def download_video(filename: str) -> bytes:
    """Download a video from the outputs volume"""
    from pathlib import Path

    video_path = Path("/outputs") / filename
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {filename}")

    return video_path.read_bytes()


# CLI functions for interacting with remote storage
@app.local_entrypoint()
def submit_loop_job(
    prompt: str,
    output_name: str = None,
    num_frames: int = 90,
    iterations_per_frame: int = 50,
    width: int = 256,
    height: int = 256,
    fps: int = 30,
    seed: int = None,
    zoom_scale: float = 1.0,
    pan_x: int = 0,
    pan_y: int = 0,
    rotate_degrees: float = 4.0,
    epochs: int = 3,
):
    """
    Submit a loop generation job to Modal (runs remotely, survives disconnects)

    Usage:
        modal run modal_video.py::submit_loop_job \\
            --prompt "steampunk godzilla" \\
            --output-name "godzilla.mp4" \\
            --num-frames 120 \\
            --rotate-degrees 3.0 \\
            --epochs 3
    """
    import time

    if output_name is None:
        # Generate filename from prompt and timestamp
        safe_prompt = "".join(c if c.isalnum() else "_" for c in prompt[:30])
        output_name = f"{safe_prompt}_{int(time.time())}.mp4"

    if not output_name.endswith(".mp4"):
        output_name += ".mp4"

    print(f"Submitting job to Modal...")
    print(f"Output: {output_name}")

    result = generate_and_save_loop.remote(
        prompt=prompt,
        output_name=output_name,
        num_frames=num_frames,
        iterations_per_frame=iterations_per_frame,
        width=width,
        height=height,
        fps=fps,
        seed=seed,
        zoom_scale=zoom_scale,
        pan_x=pan_x,
        pan_y=pan_y,
        rotate_degrees=rotate_degrees,
        epochs=epochs,
    )

    print(f"\n✓ Job completed!")
    print(f"  Filename: {result['filename']}")
    print(f"  Size: {result['size_mb']:.2f} MB")
    print(f"\nTo download:")
    print(f"  modal run modal_video.py::download_video_cli --filename {result['filename']}")


@app.local_entrypoint()
def list_videos_cli():
    """List all videos stored in Modal volume"""
    videos = list_videos.remote()

    if not videos:
        print("No videos found in storage.")
        return

    print(f"\n{'='*80}")
    print(f"Videos in Modal Storage ({len(videos)} total)")
    print(f"{'='*80}")

    for video in videos:
        import datetime
        modified = datetime.datetime.fromtimestamp(video['modified'])
        print(f"\n  {video['filename']}")
        print(f"    Size: {video['size_mb']:.2f} MB")
        print(f"    Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}")

    print(f"\n{'='*80}")
    print(f"To download a video:")
    print(f"  modal run modal_video.py::download_video_cli --filename <filename>")
    print(f"{'='*80}\n")


@app.local_entrypoint()
def download_video_cli(filename: str, output: str = None):
    """Download a video from Modal storage to local filesystem"""
    from pathlib import Path

    if output is None:
        output = filename

    print(f"Downloading {filename} from Modal storage...")

    video_bytes = download_video.remote(filename)

    output_path = Path(output)
    output_path.write_bytes(video_bytes)

    print(f"✓ Downloaded to: {output_path.absolute()}")
    print(f"  Size: {len(video_bytes) / 1024 / 1024:.2f} MB")


# ============================================================================
# Web API (Deploy this with `modal deploy modal_video.py`)
# ============================================================================

web_image = image.pip_install("fastapi[standard]")

@app.function(
    image=web_image,
    volumes={
        "/checkpoints": models_volume,
        "/outputs": outputs_volume,
    },
)
@modal.asgi_app()
def web():
    """FastAPI web interface for submitting jobs and downloading results"""
    from fastapi import FastAPI, HTTPException, Response
    from fastapi.responses import StreamingResponse, JSONResponse
    from pydantic import BaseModel
    import io

    web_app = FastAPI(
        title="VQGAN-CLIP Loop Generator",
        description="Generate perfect looping videos with VQGAN+CLIP"
    )

    class LoopJobRequest(BaseModel):
        prompt: str
        output_name: str = None
        num_frames: int = 90
        iterations_per_frame: int = 50
        width: int = 256
        height: int = 256
        fps: int = 30
        seed: int = None
        zoom_scale: float = 1.0
        pan_x: int = 0
        pan_y: int = 0
        rotate_degrees: float = 4.0
        epochs: int = 3

    @web_app.get("/")
    def read_root():
        return {
            "service": "VQGAN-CLIP Loop Generator",
            "endpoints": {
                "submit_job": "POST /jobs/submit",
                "list_videos": "GET /videos",
                "download_video": "GET /videos/{filename}",
                "job_status": "GET /jobs/{job_id}",
            }
        }

    @web_app.post("/jobs/submit")
    async def submit_job(job: LoopJobRequest):
        """Submit a video generation job (runs asynchronously)"""
        import time

        # Generate output name if not provided
        if job.output_name is None:
            safe_prompt = "".join(c if c.isalnum() else "_" for c in job.prompt[:30])
            job.output_name = f"{safe_prompt}_{int(time.time())}.mp4"

        if not job.output_name.endswith(".mp4"):
            job.output_name += ".mp4"

        # Read generate.py from the image (it's been copied to /root/generate.py)
        generate_py_code = Path("/root/generate.py").read_text()

        # Spawn the job asynchronously
        call = generate_and_save_loop.spawn(
            prompt=job.prompt,
            output_name=job.output_name,
            generate_py_code=generate_py_code,
            num_frames=job.num_frames,
            iterations_per_frame=job.iterations_per_frame,
            width=job.width,
            height=job.height,
            fps=job.fps,
            seed=job.seed,
            zoom_scale=job.zoom_scale,
            pan_x=job.pan_x,
            pan_y=job.pan_y,
            rotate_degrees=job.rotate_degrees,
            epochs=job.epochs,
        )

        return {
            "status": "submitted",
            "job_id": call.object_id,
            "output_name": job.output_name,
            "message": f"Job submitted. Check status at /jobs/{call.object_id}"
        }

    @web_app.get("/jobs/{job_id}")
    async def get_job_status(job_id: str):
        """Check the status of a submitted job"""
        from modal.functions import FunctionCall

        try:
            call = FunctionCall.from_id(job_id)

            # Try to get the result (non-blocking check)
            try:
                result = call.get(timeout=0)
                return {
                    "status": "completed",
                    "job_id": job_id,
                    "result": result
                }
            except TimeoutError:
                return {
                    "status": "running",
                    "job_id": job_id,
                    "message": "Job is still processing"
                }
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Job not found: {str(e)}")

    @web_app.get("/videos")
    async def list_all_videos():
        """List all generated videos"""
        videos = list_videos.remote()
        return {"videos": videos, "count": len(videos)}

    @web_app.get("/videos/{filename}")
    async def download_video_file(filename: str):
        """Download a specific video file"""
        try:
            video_bytes = download_video.remote(filename)
            return StreamingResponse(
                io.BytesIO(video_bytes),
                media_type="video/mp4",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}"
                }
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Video not found: {filename}")

    @web_app.delete("/videos/{filename}")
    async def delete_video_file(filename: str):
        """Delete a video from storage"""
        from pathlib import Path

        video_path = Path("/outputs") / filename
        if not video_path.exists():
            raise HTTPException(status_code=404, detail=f"Video not found: {filename}")

        video_path.unlink()
        outputs_volume.commit()

        return {"status": "deleted", "filename": filename}

    return web_app
