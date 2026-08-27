from .models import Product, ProductVersion
from rest_framework import serializers


class ProductSerializer(serializers.ModelSerializer):
    github_webhook_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'api_key', 'api_secret', 
            'webhook_token', 'github_url', 'github_webhook_url', 
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'api_key', 'api_secret', 'webhook_token', 
            'github_webhook_url', 'created_at', 'updated_at'
        ]

    def get_github_webhook_url(self, obj):
        if not obj.webhook_token:
            return None
        request = self.context.get('request')
        path = f"/github/webhook/{obj.webhook_token}/"
        if request:
            return request.build_absolute_uri(path)
        return path


class ProductVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVersion
        fields = ['id', 'product', 'version', 'description', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']