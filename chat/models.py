import uuid
from django.db import models
from django.utils import timezone
# Import your Product model from whichever app it lives in, for example:
# from authentication.models import Product 

class ChatSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Assumes 'Product' model is imported from your authentication app
    product = models.ForeignKey('authentication.Product', on_delete=models.CASCADE, related_name='chat_sessions')
    device_ip = models.GenericIPAddressField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    session_key = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Session {self.id} ({self.email or 'Anonymous'})"


class ChatMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    question = models.TextField()
    response = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message {self.id} - Session {self.session_id}"


class ChatFeedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Fixed to use ForeignKey referencing ChatSession directly (UUID type safety)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='feedback')
    rating = models.IntegerField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback {self.id} (Rating: {self.rating})"