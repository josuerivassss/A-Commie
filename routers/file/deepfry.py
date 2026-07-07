from fastapi import APIRouter, Query, Response
from PIL import Image, ImageEnhance
from services import painter

router = APIRouter(prefix="/image", tags=["Image"])

@router.get("/deepfry",
    description="Apply a deepfry filter to your image",
    response_class=Response
)
async def deepfry(
    image: str = Query(description="The image URL", examples=["https://images.com/myimage.png"]),
    size: int = Query(512, description="The size of the deepfry overlay", ge=128, le=2048)
):
    img = await painter.open_image(image, param="image")
    if img.size[0] != size or img.size[1] != size:
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    return Response(
        content=painter.prepare(ImageEnhance.Contrast(img).enhance(5)),
        media_type="image/png"
    )