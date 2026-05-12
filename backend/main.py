import os

import uvicorn

if __name__ == "__main__":
    # En Windows, el proceso hijo del reloader a veces no puede cargar extensiones nativas
    # (p. ej. pydantic_core) con "DLL load failed: Acceso denegado" por antivirus/politicas.
    # Por defecto: un solo proceso (reload off). Para hot-reload: UVICORN_RELOAD=1
    reload = os.environ.get("UVICORN_RELOAD", "").strip().lower() in ("1", "true", "yes")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=reload)
