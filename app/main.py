import os

from app.api import create_app

app = create_app(os.environ.get("DATABASE_PATH", "donaciones.db"), os.environ["JWT_SECRET"])
