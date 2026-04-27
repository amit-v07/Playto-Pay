from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

from apps.payouts.models import InvalidPayoutTransition


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, InvalidPayoutTransition):
        return Response(
            {"error": "Invalid state transition.", "detail": str(exc)},
            status=status.HTTP_409_CONFLICT,
        )

    if isinstance(exc, PermissionError):
        return Response(
            {"error": str(exc)},
            status=status.HTTP_403_FORBIDDEN,
        )

    return response
