from services.pillow.manager import painter
from services.http import HTTPClient
from services.pillow.fonts import FontCache
from services.pillow.images import ImageCache

FontsGallery = FontCache("./assets/fonts") # The gallery of the fonts loaded in cache
ImagesGallery = ImageCache("./assets/images") # The gallery of the images loaded in cache