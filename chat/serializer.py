from rest_framework import serializers
from .models import ChatSession, ChatMessage, ChatFeedback

class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = [
            'id', 'product', 'device_ip', 'email', 'session_key', 
            'is_active', 'is_resolved', 'created_at', 'ended_at'
        ]


class ChatMessageSerializer(serializers.ModelSerializer):
   
    article_ids = serializers.ListField(
        child=serializers.UUIDField(), 
        required=False, 
        default=list
    )

    class Meta:
        model = ChatMessage
        fields = ['id', 'session', 'question', 'response', 'article_ids', 'created_at']


class ChatFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatFeedback
        fields = ['id', 'session', 'rating', 'comment', 'created_at']