from fastapi import APIRouter, Query, Response
from PIL import Image
from services import painter, ImagesGallery

router = APIRouter(prefix="/image", tags=["Image"])

@router.get("/simp",
    description="Apply a simp filter to your image",
    response_class=Response
)
async def simp(
    image: str = Query(description="The image URL", examples=["https://images.com/myimage.png"]),
):
    img = await painter.open_image(image, param="image")
    overlay = ImagesGallery.get("simp").resize(img.size, Image.Resampling.LANCZOS)
    img.paste(overlay, (0, 0), overlay)
    return Response(
        content=painter.prepare(img),
        media_type="image/png"
    )