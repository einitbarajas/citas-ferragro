from typing import Any


def ok_response(data: Any = None, message: str = "OK") -> dict[str, Any]:
    return {"success": True, "data": data, "message": message}


def error_response(message: str, data: Any = None) -> dict[str, Any]:
    return {"success": False, "data": data, "message": message}
