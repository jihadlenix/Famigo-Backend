import os
import torch
import torch.nn as nn
import numpy as np
from PIL import Image
from uuid import uuid4
from torchvision import transforms
from typing import Optional

# Global model variable to load once and reuse
_model: Optional[torch.nn.Module] = None
_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class Generator(nn.Module):
    """
    White-box CartoonGAN Generator Network Architecture
    Based on the original White-box Cartoonization paper
    """
    def __init__(self):
        super(Generator, self).__init__()
        
        # Encoder
        self.encoder = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=7, stride=1, padding=3, padding_mode='reflect'),
            nn.InstanceNorm2d(64),
            nn.ReLU(inplace=True),
            
            nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1),
            nn.InstanceNorm2d(128),
            nn.ReLU(inplace=True),
            
            nn.Conv2d(128, 256, kernel_size=3, stride=2, padding=1),
            nn.InstanceNorm2d(256),
            nn.ReLU(inplace=True),
        )
        
        # Residual blocks
        res_blocks = []
        for _ in range(8):
            res_blocks.append(ResidualBlock(256))
        self.residual = nn.Sequential(*res_blocks)
        
        # Decoder
        self.decoder = nn.Sequential(
            nn.ConvTranspose2d(256, 128, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.InstanceNorm2d(128),
            nn.ReLU(inplace=True),
            
            nn.ConvTranspose2d(128, 64, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.InstanceNorm2d(64),
            nn.ReLU(inplace=True),
            
            nn.Conv2d(64, 3, kernel_size=7, stride=1, padding=3, padding_mode='reflect'),
            nn.Tanh()
        )
    
    def forward(self, x):
        x = self.encoder(x)
        x = self.residual(x)
        x = self.decoder(x)
        return x


class ResidualBlock(nn.Module):
    """Residual block for the generator"""
    def __init__(self, channels):
        super(ResidualBlock, self).__init__()
        self.conv_block = nn.Sequential(
            nn.Conv2d(channels, channels, kernel_size=3, stride=1, padding=1, padding_mode='reflect'),
            nn.InstanceNorm2d(channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, kernel_size=3, stride=1, padding=1, padding_mode='reflect'),
            nn.InstanceNorm2d(channels)
        )
    
    def forward(self, x):
        return x + self.conv_block(x)


def load_cartoongan_model():
    """
    Load White-box CartoonGAN model. This function loads the model once and caches it.
    """
    global _model
    
    if _model is not None:
        return _model
    
    try:
        print("🔄 Loading White-box CartoonGAN model...")
        
        # Create model architecture
        _model = Generator().to(_device)
        
        # Try to load pre-trained weights
        model_loaded = False
        
        # Try loading from Hugging Face Hub
        try:
            from huggingface_hub import hf_hub_download
            model_repos = [
                "vinesmsuic/White-box-Cartoonization-PyTorch",
            ]
            
            for repo_id in model_repos:
                try:
                    print(f"📥 Attempting to load weights from: {repo_id}")
                    model_path = hf_hub_download(
                        repo_id=repo_id,
                        filename="netG_float.pth",
                        cache_dir="models"
                    )
                    state_dict = torch.load(model_path, map_location=_device)
                    _model.load_state_dict(state_dict, strict=False)
                    print(f"✅ Loaded White-box CartoonGAN weights from {repo_id}")
                    model_loaded = True
                    break
                except Exception as e:
                    print(f"⚠️ Could not load from {repo_id}: {e}")
                    continue
        except Exception as e:
            print(f"⚠️ Could not load from Hugging Face: {e}")
        
        # Try loading from local files
        if not model_loaded:
            local_model_paths = [
                "models/netG_float.pth",
                "models/whitebox_cartoongan.pth",
                "models/cartoongan_generator.pth"
            ]
            
            for model_path in local_model_paths:
                if os.path.exists(model_path):
                    try:
                        state_dict = torch.load(model_path, map_location=_device)
                        _model.load_state_dict(state_dict, strict=False)
                        print(f"✅ Loaded White-box CartoonGAN from local file: {model_path}")
                        model_loaded = True
                        break
                    except Exception as e2:
                        print(f"⚠️ Could not load from {model_path}: {e2}")
                        continue
        
        if not model_loaded:
            print("⚠️ No pre-trained weights found. Using randomly initialized model.")
            print("   For best results, download pre-trained weights from:")
            print("   https://github.com/vinesmsuic/White-box-Cartoonization-PyTorch")
        
        _model.eval()
        return _model
        
    except Exception as e:
        print(f"❌ Error loading White-box CartoonGAN model: {e}")
        raise


def preprocess_image_cartoongan(image_path: str) -> torch.Tensor:
    """
    Preprocess image for White-box CartoonGAN input.
    White-box CartoonGAN expects images normalized to [-1, 1] range.
    """
    # Load image using PIL
    img = Image.open(image_path).convert("RGB")
    
    # Resize to model input size (typically 256x256 or 512x512 for CartoonGAN)
    # White-box CartoonGAN usually works with 256x256 or 512x512
    target_size = 512
    width, height = img.size
    
    # Resize maintaining aspect ratio
    if width > height:
        new_width = target_size
        new_height = int(height * (target_size / width))
    else:
        new_height = target_size
        new_width = int(width * (target_size / height))
    
    img = img.resize((new_width, new_height), Image.LANCZOS)
    
    # Pad to square if needed
    if new_width != target_size or new_height != target_size:
        # Create a square image with black padding
        new_img = Image.new("RGB", (target_size, target_size), (0, 0, 0))
        paste_x = (target_size - new_width) // 2
        paste_y = (target_size - new_height) // 2
        new_img.paste(img, (paste_x, paste_y))
        img = new_img
    
    # Convert to tensor and normalize to [-1, 1]
    transform = transforms.Compose([
        transforms.ToTensor(),  # Converts to [0, 1]
        transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])  # Normalize to [-1, 1]
    ])
    
    tensor = transform(img).unsqueeze(0)  # Add batch dimension
    return tensor.to(_device)


def postprocess_image_cartoongan(tensor: torch.Tensor) -> Image.Image:
    """
    Postprocess White-box CartoonGAN output tensor to PIL Image.
    Model outputs are in [-1, 1] range, need to convert to [0, 255].
    """
    # Remove batch dimension and move to CPU
    tensor = tensor.squeeze(0).cpu()
    
    # Denormalize from [-1, 1] to [0, 1]
    tensor = (tensor + 1.0) / 2.0
    tensor = torch.clamp(tensor, 0, 1)
    
    # Convert to numpy: CHW -> HWC
    array = tensor.permute(1, 2, 0).numpy()
    array = (array * 255).astype(np.uint8)
    
    return Image.fromarray(array)


def generate_cartoon_avatar(local_image_path: str) -> str:
    """
    Generate cartoon-style avatar using White-box CartoonGAN model.
    Note: First call will take longer (~10-20s on CPU) due to model loading.
    Subsequent calls will be faster (~2-5s on CPU) as model is cached.
    """
    print(f"🎨 Generating cartoon avatar with White-box CartoonGAN → {local_image_path}")
    
    try:
        # Load model (will cache after first load - lazy loading, only when needed)
        print("⏳ Loading White-box CartoonGAN model (this may take 10-20 seconds on first run)...")
        model = load_cartoongan_model()
        
        # Preprocess input image
        input_tensor = preprocess_image_cartoongan(local_image_path)
        
        # Generate cartoon-style image
        print("🔄 Running White-box CartoonGAN inference...")
        with torch.no_grad():
            # White-box CartoonGAN forward pass
            output_tensor = model(input_tensor)
        
        # Postprocess output
        cartoon_image = postprocess_image_cartoongan(output_tensor)
        
        # Save locally
        output_dir = "static/avatars"
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, f"avatar_{uuid4().hex}.png")
        
        cartoon_image.save(out_path, "PNG")
        
        print(f"✅ Cartoon avatar saved at {out_path}")
        return f"/{out_path}"
        
    except Exception as e:
        print(f"❌ Error generating cartoon avatar: {e}")
        import traceback
        traceback.print_exc()
        raise
