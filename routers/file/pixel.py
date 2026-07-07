from fastapi import APIRouter, Query, Response
from PIL import Image
from services import painter

router = APIRouter(prefix="/image", tags=["Image"])

@router.get("/pixel",
    description="Apply a pixel filter to your image",
    response_class=Response
)
async def pixel(
    image: str = Query(description="The image URL", examples=["https://images.com/myimage.png"]),
    size: int = Query(512, description="The size of the output image", ge=128, le=2048),
    adjust: float = Query(10.0, description="The pixelation adjustment factor", ge=0.1, le=10.0)
):
    img = await painter.open_image(image, param="image")
    if img.size[0] != size or img.size[1] != size:
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    org_size = img.size
    img = img.resize((int(img.size[0] / adjust), int(img.size[1] / adjust)), Image.Resampling.NEAREST)
    img = img.resize(org_size, Image.Resampling.NEAREST)
    return Response(
        content=painter.prepare(img),
        media_type="image/png"
    )