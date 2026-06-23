from pathlib import Path
from typing import Dict
from PIL import ImageFont


class FontCache:
    """
    Loads and caches all fonts from a directory on startup.
    Font files must follow the naming convention: FontName_Style.ttf
    Example: Roboto_Regular.ttf, Roboto_Bold.ttf, Roboto_Italic.ttf
    """

    SUPPORTED_FORMATS = ("*.ttf", "*.otf")

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        if not self.path.is_dir():
            raise ValueError(f"Invalid directory: {path}")
        self._cache: Dict[str, Dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        """Loads all supported fonts into cache on startup."""
        for pattern in self.SUPPORTED_FORMATS:
            for file in self.path.glob(pattern):
                name, *style = file.stem.split("_")
                style = style[0] if style else "Regular"
                self._cache.setdefault(name, {})[style] = str(file)

    def get(self, name: str, style: str = "Regular", size: int = 12) -> ImageFont.FreeTypeFont:
        """Returns a font variant at the requested size."""
        font_path = self._cache.get(name, {}).get(style)
        if font_path is None:
            raise KeyError(f"Font '{name}' with style '{style}' not found in cache.")
        return ImageFont.truetype(font_path, size=size)

    def reload(self) -> None:
        """Reloads all fonts from disk."""
        self._cache.clear()
        self._load()

    @property
    def loaded(self) -> Dict[str, list[str]]:
        """Returns all cached fonts and their available styles."""
        return {name: list(styles.keys()) for name, styles in self._cache.items()}

    def __contains__(self, name: str) -> bool:
        return name in self._cache

    def __len__(self) -> int:
        return len(self._cache)