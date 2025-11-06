# VQGAN-CLIP Docker Container
# Build: docker build -t vqgan-clip .
# Run: docker run --gpus all -v $(pwd)/outputs:/app/outputs vqgan-clip -p "your prompt here"

FROM nvidia/cuda:11.1.1-cudnn8-runtime-ubuntu20.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.9 \
    python3.9-dev \
    python3-pip \
    git \
    curl \
    ffmpeg \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

# Set python3.9 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.9 1
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install PyTorch with CUDA 11.1
RUN pip install --no-cache-dir \
    torch==1.9.0+cu111 \
    torchvision==0.10.0+cu111 \
    torchaudio==0.9.0 \
    -f https://download.pytorch.org/whl/torch_stable.html

# Install other dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Clone required repositories
RUN git clone https://github.com/openai/CLIP CLIP && \
    git clone https://github.com/CompVis/taming-transformers

# Copy application code
COPY generate.py .
COPY download_models.sh .

# Make download script executable
RUN chmod +x download_models.sh

# Create directories
RUN mkdir -p checkpoints outputs steps

# Download models
RUN curl -L -o checkpoints/vqgan_imagenet_f16_16384.yaml -C - \
    'https://heibox.uni-heidelberg.de/d/a7530b09fed84f80a887/files/?p=%2Fconfigs%2Fmodel.yaml&dl=1' && \
    curl -L -o checkpoints/vqgan_imagenet_f16_16384.ckpt -C - \
    'https://heibox.uni-heidelberg.de/d/a7530b09fed84f80a887/files/?p=%2Fckpts%2Flast.ckpt&dl=1'

# Set entrypoint
ENTRYPOINT ["python", "generate.py"]
CMD ["-p", "A painting of an apple in a fruit bowl", "-o", "outputs/output.png"]
