from django.db import models
import uuid

class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    api_key = models.CharField(max_length=255, unique=True)
    api_secret = models.CharField(max_length=255, blank=True, null=True)
    github_url = models.URLField(max_length=500, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ProductVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='versions')
    version = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Product Versions"       


    def __str__(self):
        return f"{self.product.name} - {self.version}"
