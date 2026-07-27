from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model

User = get_user_model()


class CookieJWTAuthentication(BaseAuthentication):
    """
    Authenticate using the access_token stored in an HttpOnly cookie.
    """

    def authenticate(self, request):
        token = request.COOKIES.get("access_token")

        if not token:
            return None

        try:
            access_token = AccessToken(token)
            user_id = access_token["user_id"]

            user = User.objects.get(id=user_id)

            return (user, token)

        except User.DoesNotExist:
            raise AuthenticationFailed("User not found.")

        except Exception as e:
            raise AuthenticationFailed(f"Invalid token: {str(e)}")