from unittest.mock import patch

from rest_framework.exceptions import APIException, ValidationError

from config.utils import exception_handler
from expenses.services import TransitionError


def test_unexpected_api_failure_has_no_traceback_or_private_details():
    error = RuntimeError("PRIVATE DATABASE DETAILS")
    with patch("config.utils.logger.error") as log, patch("config.utils.set_rollback") as rollback:
        response = exception_handler(error, {})
    assert response.status_code == 500
    assert "PRIVATE" not in str(response.data)
    assert response["Cache-Control"] == "no-store"
    log.assert_called_once()
    rollback.assert_called_once()


def test_known_server_error_is_also_sanitized():
    with patch("config.utils.logger.error"):
        response = exception_handler(APIException("PRIVATE PROVIDER ERROR"), {})
    assert response.status_code == 500
    assert "PRIVATE" not in str(response.data)


def test_business_and_validation_errors_keep_their_status():
    response = exception_handler(TransitionError("A comment is required.", 400), {})
    assert response.status_code == 400
    assert response.data["detail"] == "A comment is required."
    response = exception_handler(ValidationError({"email": ["Enter a valid email address."]}), {})
    assert response.status_code == 400
    assert "email" in response.data
