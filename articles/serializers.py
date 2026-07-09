from rest_framework import serializers
from .models import Tag, Category, Articles, ArticleTag, ArticlesVersion, ArticleImage

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'description']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']


class ArticlesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Articles
        fields = ['id', 'title', 'description', 'category', 'visibility', 'status', 'created_at', 'updated_at']


class ArticleTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleTag
        fields = ['id', 'article', 'tag']


class ArticlesVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticlesVersion
        fields = [
            'id', 'article', 'product_version', 'content', 'changes', 
            'status', 'author', 'reviewed_by', 'created_at', 'updated_at'
        ]


class ArticleImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleImage
        fields = [
            'id', 'article', 'article_version', 'file_name', 'file_path', 
            'file_size', 'mime_type', 'alt_text', 'caption', 'display_order', 
            'uploaded_by', 'created_at', 'updated_at'
        ]