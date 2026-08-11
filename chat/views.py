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


class SendMessageAPIView(APIView):
    """
    POST: Processes incoming chat messages, manages session persistence, and creates a ChatMessage record.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = SendMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        client_ip = request.META.get('REMOTE_ADDR')

        chat_message = ChatbotService.process_user_message(
            session_key=data['session_key'],
            question=data['question'],
            product_id=data.get('product_id'),
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