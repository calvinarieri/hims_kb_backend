from rest_framework import serializers
from .models import ChatSession, ChatMessage, ChatFeedback


class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ['id', 'product', 'device_ip', 'email', 'session_key', 'is_active', 'is_resolved', 'created_at']
        read_only_fields = ['id', 'created_at']


class SendMessageSerializer(serializers.Serializer):
    session_key = serializers.CharField(
        max_length=255, 
        required=True,
        help_text="Unique key for the chat session."
    )
    question = serializers.CharField(
        required=True, 
        error_messages={"blank": "Question cannot be empty."}
    )
    product_id = serializers.UUIDField(
        required=False, 
        help_text="Product UUID (required if creating a brand new session)"
    )
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'session', 'question', 'response', 'article_ids', 'created_at']
        read_only_fields = ['id', 'created_at']


class ChatFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatFeedback
        fields = ['id', 'session', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'created_at']