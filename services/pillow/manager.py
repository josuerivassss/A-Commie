import io
import typing
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
from schemas.responses import HTTPResponse

class Painter:
    """Handles all Pillow image processing operations."""

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
                from services.http import HTTPClient
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

    async def draw_text(self, image: Image.Image, **kwargs) -> None:
        """Draws text with emoji support."""
        with Pilmoji(image) as pilmoji:
            pilmoji.text(**kwargs)

    def get_metrics(self, font: ImageFont.FreeTypeFont, text: str) -> typing.Tuple[int, int]:
        """Returns the width and height of a text block."""
        if "\n" in text:
            W, H = 0, 0
            for line in text.split("\n"):
                bbox = font.getbbox(line)
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                W = max(W, w)
                H += h
            return W, H
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    def get_advanced_metrics(
        self,
        image: Image.Image,
        font: ImageFont.FreeTypeFont,
        text: str,
        spacing: int = 4
    ) -> typing.Tuple[int, int]:
        """Returns text metrics including emoji sizing."""
        with Pilmoji(image) as pilmoji:
            return pilmoji.getsize(text=text, font=font, spacing=spacing)

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


# Singleton instance
painter = Painter()