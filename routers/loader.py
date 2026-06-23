import os
import importlib
from fastapi import FastAPI

async def load_routes(app: FastAPI) -> None:
    """Dynamically loads all FastAPI routers from the routes directory."""
    routes_dir = "./routers"
    for folder in os.listdir(routes_dir):
        folder_path = os.path.join(routes_dir, folder)
        if not os.path.isdir(folder_path):
            continue
        for file in os.listdir(folder_path):
            if file.endswith(".py") and "ignore" not in file and file != "__init__.py":
                module_name = file[:-3]
                module = importlib.import_module(f"routers.{folder}.{module_name}")
                if hasattr(module, "router"):
                    app.include_router(module.router)