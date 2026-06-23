from fastapi import APIRouter, Query, Response
from services import painter, ImagesGallery, FontsGallery
from textwrap import fill

router = APIRouter(prefix="/image", tags=["Image"])

@router.get("/sonic",
    description="Apply a sonic filter to your image",
    response_class=Response
)
async def sonic(
    text: str = Query(description="The text for the image", max_lenght=150)
):
    font = FontsGallery.get("GGSans").font_variant(size=30)
    text = fill(text, 50)
    image = ImagesGallery.get("sonic").convert("RGBA")
    await painter.draw_text(image, xy=(366, 65), text=text, fill="White", font=font)
    return Response(content=painter.prepare(image), media_type="image/png")