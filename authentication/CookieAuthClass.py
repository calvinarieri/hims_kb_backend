from rest_framework.authentication import BaseAuthentication
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model

User = get_user_model()


class CookieJWTAuthentication(BaseAuthentication):
    """
    Authenticate using the access_token stored in an HttpOnly cookie or Authorization header.
    Returns None if no token or token is invalid/expired so DRF handles unauthenticated requests cleanly.
    """

    def authenticate(self, request):
        token = request.COOKIES.get("access_token")

        if not token:
            header = request.headers.get("Authorization")
            if header and header.startswith("Bearer "):
                token = header.split(" ")[1]

        if not token:
            return None

        try:
            access_token = AccessToken(token)
            user_id = access_token["user_id"]
            user = User.objects.get(id=user_id)
            return (user, token)
        except Exception:
            # If token is invalid, expired, or user does not exist, treat as unauthenticated
            return None