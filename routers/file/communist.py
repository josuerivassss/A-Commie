from fastapi import APIRouter, Query, Response
from PIL import Image
from services import painter, ImagesGallery

router = APIRouter(prefix="/image", tags=["Image"])

@router.get("/communist",
    description="Apply a communist filter to your image",
    response_class=Response
)
async def communist(
    image: str = Query(description="The image URL", examples=["https://images.com/myimage.png"]),
    size: int = Query(512, description="The size of output image", ge=128, le=2048)
):
    img = await painter.open_image(image, param="image")
    if img.size[0] != size or img.size[1] != size:
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    overlay = ImagesGallery.get("communist")
    if overlay.size[0] != size or overlay.size[1] != size:
        overlay = overlay.resize((size, size), Image.Resampling.LANCZOS)
    img.paste(overlay, (0, 0), overlay)
    return Response(
        content=painter.prepare(img),
        media_type="image/png"
    )