from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler, set_rollback
import logging

logger = logging.getLogger(__name__)


def exception_handler(exc, context):
    """Turn known service errors into JSON {detail: ...} payloads."""
    from expenses.services import TransitionError

    if isinstance(exc, TransitionError):
        return Response({"detail": exc.message}, status=exc.status_code)

    response = drf_exception_handler(exc, context)
    if response is None or response.status_code >= 500:
        set_rollback()
        # Keep diagnostics server-side, even when DEBUG is enabled locally.
        logger.error("Unhandled Homebase API error", exc_info=(type(exc), exc, exc.__traceback__))
        return Response({"detail": "We couldn't complete your request. Please try again shortly."},
                        status=response.status_code if response is not None else 500,
                        headers={"Cache-Control": "no-store"})
    return response
