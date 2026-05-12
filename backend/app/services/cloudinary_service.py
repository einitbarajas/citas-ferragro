from fastapi import HTTPException
import cloudinary
import cloudinary.uploader

from app.core.config import settings

_configured = False


def _configure_once() -> None:
    global _configured
    if _configured:
        return
    if not settings.cloudinary_cloud_name or not settings.cloudinary_api_key or not settings.cloudinary_api_secret:
        raise HTTPException(
            status_code=500,
            detail="Cloudinary no está configurado en variables de entorno.",
        )
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    _configured = True


def upload_profile_photo(file_bytes: bytes, filename: str) -> str:
    _configure_once()
    try:
        result = cloudinary.uploader.upload(
            file_bytes,
            resource_type="image",
            folder=settings.cloudinary_folder,
            public_id=None,
            overwrite=True,
            filename_override=filename,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo subir la imagen a Cloudinary: {exc}",
        ) from exc
    url = str(result.get("secure_url") or "").strip()
    if not url:
        raise HTTPException(status_code=500, detail="No se pudo obtener la URL de la imagen en Cloudinary.")
    return url
