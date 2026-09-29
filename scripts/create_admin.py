"""Ejecutar como módulo: python -m scripts.create_admin."""
import getpass
import os

from app.api import Credentials
from app.core import create_user, initialize

if __name__ == "__main__":
    data = Credentials(email=input("Correo del administrador: "), password=getpass.getpass("Contraseña (12+ caracteres): "))
    path = os.environ.get("DATABASE_PATH", "donaciones.db")
    initialize(path)
    create_user(path, str(data.email), data.password, "administrador")
    print("Administrador creado. No se permite elegir este rol desde el registro público.")
