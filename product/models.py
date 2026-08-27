from django.db import models
import uuid
import secrets


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    api_key = models.CharField(max_length=255, unique=True, blank=True, null=True)
    api_secret = models.CharField(max_length=255, blank=True, null=True)
    webhook_token = models.CharField(max_length=255, unique=True, blank=True, null=True)
    github_url = models.URLField(max_length=500, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = f"hk_live_{secrets.token_urlsafe(24)}"
        if not self.api_secret:
            self.api_secret = f"hs_live_{secrets.token_urlsafe(32)}"
        if not self.webhook_token:
            self.webhook_token = f"whk_{secrets.token_urlsafe(24)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='versions')
    version = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ('pending', 'PENDING'),
            ('approved', 'APPROVED'),
            ('declined', 'DECLINED'),
        ],
        default='pending'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Product Versions"

    def __str__(self):
        return f"{self.product.name} - {self.version}"
