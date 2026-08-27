# myapp/middleware.py
import logging
from rest_framework import response, status

logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        # This triggers only when a view raises an unhandled exception
        logger.error(f"Server Error occurred: {str(exception)}", exc_info=True)
        
        # Return a uniform format for your frontend/API clients
        return response.Response({
            "error": "Internal Server Error",
            "message": "An unexpected error occurred on the server."
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
