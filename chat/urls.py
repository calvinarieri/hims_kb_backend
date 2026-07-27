from django.urls import path
from .views import SendMessageAPIView, SessionHistoryAPIView, ChatFeedbackAPIView

app_name = "chatbot"

urlpatterns = [
    path("send/", SendMessageAPIView.as_view(), name="send_message"),
    path("history/<str:session_key>/", SessionHistoryAPIView.as_view(), name="session_history"),
    path("feedback/", ChatFeedbackAPIView.as_view(), name="submit_feedback"),
]