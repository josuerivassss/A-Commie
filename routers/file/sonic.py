from fastapi import APIRouter, Query, Response
from services import painter, ImagesGallery, FontsGallery

router = APIRouter(prefix="/image", tags=["Image"])

@router.get("/sonic",
    description="Apply a sonic filter to your image",
    response_class=Response
)
async def sonic(
    text: str = Query(description="The text for the image", max_lenght=150)
):
    font = FontsGallery.get("GGSans").font_variant(size=50)
    text = painter.wrap_text(text, font, 350)
    image = ImagesGallery.get("sonic").convert("RGBA")
    await painter.render_text(image, (365, 65), text, font, fill="White")
    return Response(content=painter.prepare(image), media_type="image/png")