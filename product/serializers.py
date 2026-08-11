from .models import *
from rest_framework import serializers

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'api_key', 'api_secret', 'created_at', 'updated_at']
        extra_kwargs = {
            'api_secret': {'write_only': True, 'required': True}
        }



class ProductVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVersion
        fields = ['id', 'product', 'version', 'description', 'created_at']