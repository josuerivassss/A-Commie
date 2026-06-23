from fastapi import APIRouter, Query, Response
from PIL import ImageFilter
from services import painter

router = APIRouter(prefix="/image", tags=["Image"])

@router.get("/blur",
    description="Apply a blur filter to your image",
    response_class=Response
)
async def blur(
    image: str = Query(description="The image URL", examples=["https://images.com/myimage.png"]),
    radius: int = Query(2, description="The radius for the blur", ge=1, le=10)
):
    img = await painter.open_image(image, param="image")
    return Response(
        content=painter.prepare(img.filter(ImageFilter.GaussianBlur(radius))),
        media_type="image/png"
    )