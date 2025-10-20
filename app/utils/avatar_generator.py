import cv2
import os
from uuid import uuid4

def generate_cartoon_avatar(local_image_path: str) -> str:
    """
    Offline cartoonizer using OpenCV — runs fully locally.
    """

    print(f"🎨 Cartoonizing locally → {local_image_path}")

    # Load image
    img = cv2.imread(local_image_path)
    if img is None:
        raise Exception("Could not read the input image")

    # Resize for consistent output
    img = cv2.resize(img, (512, 512))

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)

    # Detect edges
    edges = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY,
        9, 9
    )

    # Apply bilateral filter to smooth colors
    color = cv2.bilateralFilter(img, 9, 250, 250)

    # Combine edges + color for cartoon look
    cartoon = cv2.bitwise_and(color, color, mask=edges)

    # Save locally
    output_dir = "static/avatars"
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"avatar_{uuid4().hex}.png")

    cv2.imwrite(out_path, cartoon)

    print(f"✅ Cartoon avatar saved at {out_path}")
    return f"/{out_path}"
