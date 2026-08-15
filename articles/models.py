import uuid
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.conf import settings
from authentication.models import *
from product.models import *

try:
    from pgvector.django import VectorField
except Exception:  # pragma: no cover
    VectorField = None

class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Articles(models.Model):
    VISIBILITY_CHOICES = [
        ('PUBLIC', 'Public'),
        ('PRIVATE', 'Private'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('REVIEW', 'Review'),
        ('PUBLISHED', 'Published')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='articles')
    visibility = models.CharField(max_length=50, choices=VISIBILITY_CHOICES)
    status = models.CharField(max_length=50, default='DRAFT', choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Articles"

    def __str__(self):
        return self.title


class ArticleTag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    article = models.ForeignKey(Articles, on_delete=models.CASCADE, related_name='article_tags')
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name='tag_articles')

    class Meta:
        unique_together = ('article', 'tag')  



class ArticlesVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    article = models.ForeignKey(Articles, on_delete=models.CASCADE, related_name='versions')
    product_version = models.ForeignKey(ProductVersion, on_delete=models.CASCADE, related_name='article_versions')
    content = models.TextField()
    changes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50)
    embedding = (
        VectorField(dimensions=1536, null=True, blank=True)
        if VectorField is not None
        else ArrayField(models.FloatField(), size=1536, null=True, blank=True, default=list)
    )

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='authored_versions')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_versions')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.article.title} - Version {self.product_version}"


class ArticleImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    article = models.ForeignKey(Articles, on_delete=models.CASCADE, related_name='images')
    article_version = models.ForeignKey(ArticlesVersion, on_delete=models.CASCADE, related_name='images')
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)  # Or use models.ImageField if handling files directly
    file_size = models.IntegerField()
    mime_type = models.CharField(max_length=100)
    alt_text = models.CharField(max_length=255, blank=True, null=True)
    caption = models.TextField(blank=True, null=True)
    display_order = models.IntegerField(default=0)
    
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_images')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.file_name