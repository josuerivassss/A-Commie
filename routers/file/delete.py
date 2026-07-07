from fastapi import APIRouter, Query, Response
from PIL import Image
from services import painter, ImagesGallery

router = APIRouter(prefix="/image", tags=["Image"])

@router.get("/delete",
    description="Apply a delete filter to your image",
    response_class=Response
)
async def delete(
    image: str = Query(description="The image URL", examples=["https://images.com/myimage.png"]),
    size: int = Query(512, description="The size of the output image", ge=128, le=2048)
):
    img = await painter.open_image(image, param="image")
    img = img.resize((180, 180), Image.Resampling.LANCZOS)
    background = ImagesGallery.get("delete").resize((size, size))
    background.paste(img, (0, 0), img)
    return Response(
        content=painter.prepare(background),
        media_type="image/png"
    )