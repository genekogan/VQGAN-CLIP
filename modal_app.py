"""
VQGAN-CLIP on Modal with GPU support
Run with: modal run modal_app.py --prompt "your text prompt here"
"""

import modal
from pathlib import Path

# Create Modal app
app = modal.App("vqgan-clip")

# Create a volume for model checkpoints (persists between runs)
volume = modal.Volume.from_name("vqgan-models", create_if_missing=True)

# Define the image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.9")
    .apt_install("git", "curl", "ffmpeg", "imagemagick")
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
        "torchmetrics==0.3.2",  # Pin compatible version
        "IPython",
        "kornia==0.5.4",
        "imageio",
        "imageio-ffmpeg",
        "einops",
        "torch-optimizer",
        "setuptools==59.5.0",
        "Pillow==8.2.0",
        "requests",  # Required by taming-transformers
    )
    .run_commands(
        "git clone https://github.com/openai/CLIP /clip",
        "git clone https://github.com/CompVis/taming-transformers /taming-transformers",
    )
    .add_local_file("generate.py", "/generate.py")
)


@app.function(
    image=image,
    gpu="T4",  # Use T4 GPU (cheaper, good for this workload)
    timeout=3600,  # 1 hour timeout
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
    return str(checkpoint_dir)


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
):
    """Generate an image from a text prompt using VQGAN-CLIP"""
    import sys
    import torch
    from pathlib import Path
    import random

    # Add paths for CLIP and taming-transformers
    sys.path.append('/clip')
    sys.path.append('/taming-transformers')

    # Import after path setup
    from omegaconf import OmegaConf
    from taming.models import vqgan
    import clip as openai_clip
    from PIL import Image
    import numpy as np
    from torch import nn, optim
    from torch.nn import functional as F
    from torchvision import transforms
    from torchvision.transforms import functional as TF
    import kornia.augmentation as K
    from torch_optimizer import DiffGrad, AdamP

    # Set device
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print(f'Using device: {device}')

    # Set seed
    if seed is None:
        seed = random.randint(0, 2**32 - 1)
    print(f'Using seed: {seed}')
    torch.manual_seed(seed)

    # Load VQGAN model
    checkpoint_dir = Path("/checkpoints")
    config_path = checkpoint_dir / "vqgan_imagenet_f16_16384.yaml"
    checkpoint_path = checkpoint_dir / "vqgan_imagenet_f16_16384.ckpt"

    config = OmegaConf.load(config_path)
    model = vqgan.VQModel(**config.model.params)
    model.eval().requires_grad_(False)
    model.init_from_ckpt(str(checkpoint_path))
    model = model.to(device)

    # Load CLIP model
    perceptor, preprocess = openai_clip.load('ViT-B/32', device=device, jit=False)
    perceptor.eval().requires_grad_(False)

    # Image size calculations
    f = 2**(model.decoder.num_resolutions - 1)
    toksX, toksY = image_size[0] // f, image_size[1] // f
    sideX, sideY = toksX * f, toksY * f

    # Initialize image
    z_min = model.quantize.embedding.weight.min(dim=0).values[None, :, None, None]
    z_max = model.quantize.embedding.weight.max(dim=0).values[None, :, None, None]

    z = torch.randn([1, model.quantize.e_dim, toksY, toksX], device=device)
    z = z * 2 - 1
    z = z.requires_grad_(True)

    # Setup optimizer
    opt = optim.Adam([z], lr=0.1)

    # Normalize function for CLIP
    normalize = transforms.Normalize(mean=[0.48145466, 0.4578275, 0.40821073],
                                    std=[0.26862954, 0.26130258, 0.27577711])

    # Parse prompts
    texts = [phrase.strip() for phrase in prompt.split("|")]
    target_embeds = []
    weights = []

    for text in texts:
        if ":" in text:
            text, weight = text.rsplit(":", 1)
            weight = float(weight)
        else:
            weight = 1.0

        target_embeds.append(perceptor.encode_text(openai_clip.tokenize(text).to(device)).float())
        weights.append(weight)

    weights = torch.tensor(weights, device=device)
    weights = weights / weights.sum()

    # Augmentation pipeline
    augs = nn.Sequential(
        K.RandomAffine(degrees=15, translate=0.1, p=0.7, padding_mode='border'),
        K.RandomPerspective(0.7, p=0.7),
        K.ColorJitter(hue=0.1, saturation=0.1, p=0.7),
        K.RandomErasing((.1, .4), (.3, 1/.3), same_on_batch=True, p=0.7),
    )

    # Generate
    print(f'Generating image for prompt: "{prompt}"')
    print(f'Image size: {sideX}x{sideY}, Iterations: {iterations}')

    for i in range(iterations):
        opt.zero_grad()

        # Clamp z
        z.data = z.data.clamp(z_min, z_max)

        # Decode image
        x = model.decode(model.quantize.get_codebook_entry(
            model.quantize.embedding(z.movedim(1, 3).flatten(0, 2)).view(1, toksY, toksX, -1).movedim(3, 1),
            shape=[1, toksY, toksX, model.quantize.e_dim]
        )[0])

        x = torch.sigmoid(x)

        # Apply augmentations
        into = augs(x.add(1).div(2))
        into = normalize(into)

        # Encode with CLIP
        image_embeds = perceptor.encode_image(into).float()

        # Calculate loss
        losses = []
        for target_embed, weight in zip(target_embeds, weights):
            loss = -100 * torch.cosine_similarity(image_embeds, target_embed).mean() * weight
            losses.append(loss)

        loss = sum(losses)
        loss.backward()
        opt.step()

        if i % 50 == 0:
            print(f'Iteration {i}/{iterations}, Loss: {loss.item():.4f}')

    # Final image
    with torch.no_grad():
        x = model.decode(model.quantize.get_codebook_entry(
            model.quantize.embedding(z.movedim(1, 3).flatten(0, 2)).view(1, toksY, toksX, -1).movedim(3, 1),
            shape=[1, toksY, toksX, model.quantize.e_dim]
        )[0])
        x = torch.sigmoid(x)

    # Convert to PIL Image
    img_array = x[0].cpu().detach().numpy()
    img_array = np.transpose(img_array, (1, 2, 0))
    img_array = (img_array * 255).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(img_array)

    # Save to bytes
    import io
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    print("Image generation complete!")
    return img_bytes.read()


@app.local_entrypoint()
def main(
    prompt: str = "A painting of an apple in a fruit bowl",
    iterations: int = 500,
    width: int = 512,
    height: int = 512,
    seed: int = None,
    output: str = "output.png",
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
    """
    import sys
    from pathlib import Path

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
    )

    # Save locally
    output_path = Path(output)
    output_path.write_bytes(img_bytes)
    print(f"\nImage saved to: {output_path.absolute()}")
