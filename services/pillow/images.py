from pathlib import Path
from typing import Dict
from PIL import Image

class ImageCache:
    """
    Loads and caches all images from a directory on startup.
    Returns copies to prevent mutation of cached originals.
    """

    SUPPORTED_FORMATS = ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif")

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        if not self.path.is_dir():
            raise ValueError(f"Invalid directory: {path}")
        self._cache: Dict[str, Image.Image] = {}
        self._load()

    def _load(self) -> None:
        """Loads all supported images into cache on startup."""
        for pattern in self.SUPPORTED_FORMATS:
            for file in self.path.glob(pattern):
                self._cache[file.stem] = Image.open(file).copy()

    def get(self, name: str, mode: str = "RGBA") -> Image.Image:
        """Returns a copy of the cached image in the requested mode."""
        image = self._cache.get(name)
        if image is None:
            raise KeyError(f"Image '{name}' not found in cache.")
        return image.convert(mode).copy()

    def reload(self) -> None:
        """Reloads all images from disk, useful for hot-reloading assets."""
        self._cache.clear()
        self._load()

    def preload(self, name: str, image: Image.Image) -> None:
        """Manually adds an image to the cache at runtime."""
        self._cache[name] = image.copy()

    @property
    def loaded(self) -> list[str]:
        """Returns a list of all cached image names."""
        return list(self._cache.keys())

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, name: str) -> bool:
        return name in self._cache