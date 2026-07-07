import io
import typing
import emoji
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from schemas.responses import HTTPResponse
from services.http import HTTPClient
from io import BytesIO

class Painter:
    """Handles all Pillow image processing operations."""
    EMOJI_CDN = "https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/72x72/"
    _emoji_cache: dict[str, Image.Image] = {}

    async def open_image(
        self,
        data: str,
        mode: typing.Literal["RGB", "RGBA"] = "RGBA",
        param: str | None = None
    ) -> Image.Image:
        """Opens a local or remote image and returns it."""
        if not data and param:
            HTTPResponse.fail(status=422, error="Missing image URL", data={"loc": param, "param_type": "query"})

        if data.startswith("path:"):
            try:
                with Image.open(data.replace("path:", "")) as img:
                    return img.convert(mode)
            except Exception:
                pass
        else:
            try:
                r = await HTTPClient.get(url=data)
                with Image.open(io.BytesIO(r)) as img:
                    return img.convert(mode)
            except Exception:
                if param:
                    HTTPResponse.fail(status=422, error="Invalid image URL provided", data={"loc": param, "param_type": "query"})

    def prepare(self, image: Image.Image, format: str = "PNG") -> bytes:
        """Prepares the final image result as bytes."""
        bio = io.BytesIO()
        image.save(bio, format)
        bio.seek(0, 0) if format.lower() == "gif" else bio.seek(0)
        return bio.getvalue()

    def ellipse(self, image: Image.Image) -> Image.Image:
        """Returns the image clipped to an ellipse."""
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, *image.size), fill=255)
        image.putalpha(mask)
        return image

    def apply_rounded_borders(self, image: Image.Image, radius: int = 10) -> Image.Image:
        """Returns the image with rounded corners."""
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, *image.size), radius, fill=255)
        image.putalpha(mask)
        return image

    def _kmeans(self, pixels: np.ndarray, k: int, max_iter: int = 100) -> np.ndarray:
        """Internal k-means clustering for dominant color extraction."""
        centroids = pixels[np.random.choice(pixels.shape[0], size=k, replace=False)]
        for _ in range(max_iter):
            distances = np.sqrt(((pixels - centroids[:, np.newaxis]) ** 2).sum(axis=2))
            closest = np.argmin(distances, axis=0)
            new_centroids = np.array([
                pixels[closest == i].mean(axis=0) if len(pixels[closest == i]) > 0 else centroids[i]
                for i in range(k)
            ])
            if np.all(centroids == new_centroids):
                break
            centroids = new_centroids
        return centroids

    def get_dominant_colors(self, img: Image.Image, colors: int = 2) -> typing.List[typing.List[int]]:
        """Returns the most dominant colors in an image using k-means clustering."""
        img = img.resize((img.size[0] // 2, img.size[1] // 2)).convert("RGBA")
        pixels = np.array(img).reshape(-1, 4)
        centroids = self._kmeans(pixels, colors)
        closest = np.argmin(np.sqrt(((pixels - centroids[:, np.newaxis]) ** 2).sum(axis=2)), axis=0)
        cluster_counts = np.bincount(closest, minlength=colors)
        pairwise = np.sqrt(((centroids[:, None] - centroids[None]) ** 2).sum(axis=2))
        scores = cluster_counts * (1 / (1 + pairwise.sum(axis=0)))
        sorted_indices = np.argsort(scores)[::-1]
        return [list(map(int, centroids[i])) for i in sorted_indices[:colors]]

    async def draw_gradient(
        self,
        base: Image.Image,
        xywh: typing.Tuple[typing.Tuple[int, int], typing.Tuple[int, int]],
        colors: typing.List[typing.Tuple[int, int, int, int]],
        direction: typing.Literal["vertical", "horizontal"] = "vertical"
    ) -> None:
        """Draws a multi-color gradient onto the base image."""
        if len(colors) < 2:
            raise ValueError("At least two colors are required for a gradient.")

        (x, y), (W, H) = xywh
        use = H if direction == "vertical" else W
        gradient = []

        for i in range(use):
            index = int(i / use * (len(colors) - 1))
            r1, g1, b1, a1 = colors[index]
            r2, g2, b2, a2 = colors[index + 1]
            ratio = i / use * len(colors) - index
            gradient.append((
                int(r1 * (1 - ratio) + r2 * ratio),
                int(g1 * (1 - ratio) + g2 * ratio),
                int(b1 * (1 - ratio) + b2 * ratio),
            ))

        d = ImageDraw.Draw(base)
        for i, color in enumerate(gradient):
            if direction == "vertical":
                d.line((x, y + i, x + W, y + i + 1), fill=color, width=1)
            else:
                d.line((x + i, y, x + i + 1, y + H), fill=color, width=1)
    
    async def _get_emoji_image(self, emoji_char: str, size: int = 72) -> Image.Image | None:
        """Fetch (and cache) an emoji glyph image from the Twemoji CDN."""
        cache_key = f"{emoji_char}_{size}"
        if cache_key in self._emoji_cache:
            return self._emoji_cache[cache_key].copy()
        try:
            codepoint = "-".join(f"{ord(c):x}" for c in emoji_char)
            image_bytes = await HTTPClient.get(url=f"{self.EMOJI_CDN}{codepoint}.png", get="bytes")
            if image_bytes:
                emoji_img = Image.open(BytesIO(image_bytes)).convert("RGBA")
                emoji_img = emoji_img.resize((size, size), Image.Resampling.LANCZOS)
                self._emoji_cache[cache_key] = emoji_img
                return emoji_img.copy()
        except Exception:
            pass
        return None
    
    def _parse_text_with_emojis(self, text: str) -> list[tuple[str, bool]]:
        """Split text into (segment, is_emoji) runs."""
        segments: list[tuple[str, bool]] = []
        buffer = ""
        for char in text:
            if char in emoji.EMOJI_DATA:
                if buffer:
                    segments.append((buffer, False))
                    buffer = ""
                segments.append((char, True))
            else:
                buffer += char
        if buffer:
            segments.append((buffer, False))
        return segments
    
    async def render_text(
        self,
        image: Image.Image,
        xy: tuple[int, int],
        text: str,
        font: ImageFont.FreeTypeFont,
        fill: tuple[int, int, int, int] = (255, 255, 255, 255),
        spacing: int = 4,
        align: str = "left",
        emoji_scale: float = 0.8,
        stroke_width: int = 0,
        stroke_fill: tuple[int, int, int, int] = (0, 0, 0, 255),
        max_width: int | None = None,
    ) -> None:
        """Draw multi-line, emoji-aware text onto `image` in place."""
        draw = ImageDraw.Draw(image)
        x, y = xy
        emoji_size = int(font.size * emoji_scale)

        for line in text.split("\n"):
            segments = self._parse_text_with_emojis(line)
            line_width = sum(
                emoji_size + 2 if is_emoji else (font.getbbox(seg)[2] - font.getbbox(seg)[0])
                for seg, is_emoji in segments
            )
            if align == "center" and max_width:
                current_x = x + (max_width - line_width) // 2
            elif align == "right" and max_width:
                current_x = x + (max_width - line_width)
            else:
                current_x = x

            for segment, is_emoji in segments:
                if is_emoji:
                    emoji_img = await self._get_emoji_image(segment, emoji_size)
                    if emoji_img:
                        image.paste(emoji_img, (current_x, y + (font.size - emoji_size) // 2), emoji_img)
                        current_x += emoji_size + 2
                else:
                    draw.text(
                        (current_x, y), segment, font=font, fill=fill,
                        stroke_width=stroke_width, stroke_fill=stroke_fill,
                    )
                    bbox = font.getbbox(segment)
                    current_x += bbox[2] - bbox[0]
            y += font.size + spacing

    async def measure_text(
        self, font: ImageFont.FreeTypeFont, text: str, spacing: int = 4, emoji_scale: float = 1.0
    ) -> tuple[int, int]:
        """Measure the pixel (width, height) of emoji-aware multi-line text."""
        emoji_size = int(font.size * emoji_scale)
        max_width, total_height = 0, 0
        lines = text.split("\n")
        for idx, line in enumerate(lines):
            segments = self._parse_text_with_emojis(line)
            line_width = sum(
                emoji_size + 2 if is_emoji else (font.getbbox(seg)[2] - font.getbbox(seg)[0])
                for seg, is_emoji in segments
            )
            max_width = max(max_width, line_width)
            total_height += font.size + (spacing if idx < len(lines) - 1 else 0)
        return max_width, total_height

    def wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int, emoji_scale: float = 1.0) -> str:
        """Insert newlines so `text` fits within `max_width` pixels."""
        words = text.split(" ")
        lines: list[str] = []
        current: list[str] = []
        emoji_size = int(font.size * emoji_scale)

        for word in words:
            test_line = " ".join([*current, word])
            segments = self._parse_text_with_emojis(test_line)
            line_width = sum(
                emoji_size + 2 if is_emoji else (font.getbbox(seg)[2] - font.getbbox(seg)[0])
                for seg, is_emoji in segments
            )
            if line_width <= max_width:
                current.append(word)
            elif current:
                lines.append(" ".join(current))
                current = [word]
            else:
                lines.append(word)  # single word wider than max_width: emit anyway

        if current:
            lines.append(" ".join(current))
        return "\n".join(lines)

    def calculate_text_bbox(self, font: ImageFont.FreeTypeFont, text: str) -> tuple[int, int]:
        """Fast (no-emoji) bounding box for possibly multi-line text."""
        if "\n" not in text:
            bbox = font.getbbox(text)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        max_width, total_height = 0, 0
        for line in text.split("\n"):
            bbox = font.getbbox(line)
            max_width = max(max_width, bbox[2] - bbox[0])
            total_height += bbox[3] - bbox[1]
        return max_width, total_height


# Singleton instance
painter = Painter()