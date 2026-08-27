from django.urls import path
from .views import GithubMergeWebhookView

urlpatterns = [
    path('webhook/<str:webhook_token>/', GithubMergeWebhookView.as_view(), name='github-webhook-token'),
    path('webhook/', GithubMergeWebhookView.as_view(), name='github-webhook'),
]

