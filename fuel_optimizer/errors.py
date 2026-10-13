from django.core.exceptions import RequestDataTooBig
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class PlanningError(APIException):
    def __init__(self, code, message, status=422, details=None):
        self.status_code = status
        self.error_code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def exception_handler(exc, context):
    request = context.get("request")
    request_id = getattr(request, "request_id", "")
    if isinstance(exc, RequestDataTooBig):
        return Response(
            {
                "error": {
                    "code": "request_too_large",
                    "message": "JSON request exceeds 16 KiB.",
                    "details": {},
                    "request_id": request_id,
                }
            },
            status=400,
        )
    if isinstance(exc, PlanningError):
        return Response(
            {
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": request_id,
                }
            },
            status=exc.status_code,
        )
    response = drf_exception_handler(exc, context)
    if response is not None:
        response.data = {
            "error": {
                "code": "validation_error"
                if response.status_code == 400
                else str(getattr(exc, "default_code", "request_error")),
                "message": "Request could not be processed.",
                "details": response.data,
                "request_id": request_id,
            }
        }
    return response
