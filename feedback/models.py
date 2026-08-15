from django.db import models
import uuid
from articles.models import Articles


class ArticleFeedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    article = models.ForeignKey(Articles, on_delete=models.CASCADE, related_name='feedback')
    rating = models.IntegerField(null=True, blank=True)
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ArticleFeedback {self.id} (Article: {self.article_id})"
from django.db import models

# Create your models here.
