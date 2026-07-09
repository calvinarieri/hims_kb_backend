from rest_framework import serializers
from .models import *

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'password', 
            'role', 'is_active', 'is_staff', 'is_superuser', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'required': True},
            'is_staff': {'read_only': True},
            'is_superuser': {'read_only': True}
        }


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