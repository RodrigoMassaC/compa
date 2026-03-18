"""
Excepciones personalizadas de Compa y sus handlers para FastAPI.

Uso:
    from app.core.exceptions import NotFoundError, UnauthorizedError
    raise NotFoundError("Producto no encontrado")

Registrar en main.py:
    from app.core.exceptions import add_exception_handlers
    add_exception_handlers(app)
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


# ── Clases base ──────────────────────────────────────────────────────────────

class CompaError(Exception):
    """Excepción base del proyecto. Todas las demás heredan de aquí."""
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, detail: str = "Error interno del servidor"):
        self.detail = detail
        super().__init__(detail)


# ── Excepciones HTTP ─────────────────────────────────────────────────────────

class NotFoundError(CompaError):
    """404 — Recurso no encontrado."""
    status_code = 404
    error_code = "NOT_FOUND"

    def __init__(self, detail: str = "Recurso no encontrado"):
        super().__init__(detail)


class UnauthorizedError(CompaError):
    """401 — No autenticado o token inválido."""
    status_code = 401
    error_code = "UNAUTHORIZED"

    def __init__(self, detail: str = "Autenticación requerida"):
        super().__init__(detail)


class ForbiddenError(CompaError):
    """403 — Autenticado pero sin permisos suficientes."""
    status_code = 403
    error_code = "FORBIDDEN"

    def __init__(self, detail: str = "No tienes permiso para esta acción"):
        super().__init__(detail)


class ValidationError(CompaError):
    """422 — Datos de entrada inválidos."""
    status_code = 422
    error_code = "VALIDATION_ERROR"

    def __init__(self, detail: str = "Datos de entrada inválidos"):
        super().__init__(detail)


class RateLimitError(CompaError):
    """429 — Límite de solicitudes superado."""
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, detail: str = "Has superado el límite de consultas. Intenta más tarde."):
        super().__init__(detail)


class PlanLimitError(CompaError):
    """402 — Funcionalidad no disponible en el plan actual."""
    status_code = 402
    error_code = "PLAN_LIMIT_REACHED"

    def __init__(self, detail: str = "Esta función requiere un plan superior"):
        super().__init__(detail)


# ── Handler genérico ─────────────────────────────────────────────────────────

async def _compa_error_handler(request: Request, exc: CompaError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "detail": exc.detail,
        },
    )


# ── Registro en la app ───────────────────────────────────────────────────────

def add_exception_handlers(app: FastAPI) -> None:
    """
    Registra todos los handlers de excepciones en la app FastAPI.
    Llamar desde main.py después de crear la instancia.
    """
    app.add_exception_handler(CompaError, _compa_error_handler)
    app.add_exception_handler(NotFoundError, _compa_error_handler)
    app.add_exception_handler(UnauthorizedError, _compa_error_handler)
    app.add_exception_handler(ForbiddenError, _compa_error_handler)
    app.add_exception_handler(ValidationError, _compa_error_handler)
    app.add_exception_handler(RateLimitError, _compa_error_handler)
    app.add_exception_handler(PlanLimitError, _compa_error_handler)
