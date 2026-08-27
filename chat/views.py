from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import AllowAny

from .models import ChatMessage
from .serializers import (
    SendMessageSerializer,
    ChatMessageSerializer,
    ChatFeedbackSerializer,

)
from .services import ChatbotService


from product.models import Product


def get_product_from_request(request, data=None):
    """
    Extracts and validates Product API Key from:
    1. Header: X-API-Key or Authorization: Bearer hk_live_...
    2. Request data or Query param: api_key
    Returns (product, None) if valid, or (None, error_response) if invalid key provided.
    """
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer hk_"):
            api_key = auth_header.split(" ")[1]
    if not api_key and data and isinstance(data, dict):
        api_key = data.get("api_key")
    if not api_key:
        api_key = request.query_params.get("api_key")

    if not api_key:
        return None, None

    try:
        product = Product.objects.get(api_key=api_key)
        return product, None
    except Product.DoesNotExist:
        return None, Response(
            {"detail": "Invalid Product API Key provided."},
            status=status.HTTP_401_UNAUTHORIZED
        )


class SendMessageAPIView(APIView):
    """
    POST: Processes incoming chat messages, manages session persistence, and creates a ChatMessage record.
    Authenticates using Product API Key passed via X-API-Key header or api_key payload parameter.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = SendMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Authenticate via Product API Key if supplied
        product, err_res = get_product_from_request(request, data=data)
        if err_res:
            return err_res

        product_id = product.id if product else data.get('product_id')
        client_ip = request.META.get('REMOTE_ADDR')

        chat_message = ChatbotService.process_user_message(
            session_key=data['session_key'],
            question=data['question'],
            product_id=product_id,
            email=data.get('email'),
            client_ip=client_ip
        )

        return Response(ChatMessageSerializer(chat_message).data, status=status.HTTP_201_CREATED)


class SessionHistoryAPIView(generics.ListAPIView):
    """
    GET: Retrieves all messages for a specific session_key (used when re-opening chat widget).
    """
    permission_classes = [AllowAny]
    serializer_class = ChatMessageSerializer

    def get_queryset(self):
        session_key = self.kwargs.get('session_key')
        return ChatMessage.objects.filter(session__session_key=session_key).order_by('created_at')


class ChatFeedbackAPIView(generics.CreateAPIView):
    """
    POST: Submit feedback for a chat session.
    """
    permission_classes = [AllowAny]
    serializer_class = ChatFeedbackSerializer