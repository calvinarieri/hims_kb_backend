from rest_framework import serializers
from .models import *

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'description']
        read_only_fields = ['id']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']
        read_only_fields = ['id']


class ArticleTagSerializer(serializers.ModelSerializer):
    tag = TagSerializer(read_only=True)
    tag_id = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), source='tag', write_only=True
    )

    class Meta:
        model = ArticleTag
        fields = ['id', 'article', 'tag', 'tag_id']
        read_only_fields = ['id']


class ArticlesVersionSerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')

    class Meta:
        model = ArticlesVersion
        fields = [
            'id', 'article', 'product_version', 'content', 'changes', 
            'status', 'author', 'author_username', 'reviewed_by', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author', 'created_at', 'updated_at']


class ArticleImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleImage
        fields = [
            'id', 'article', 'article_version', 'file_name', 'file_path', 
            'file_size', 'mime_type', 'alt_text', 'caption', 'display_order', 
            'uploaded_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ArticlesSerializer(serializers.ModelSerializer):

    content = serializers.CharField(write_only=True, required=True)
    product_version = serializers.PrimaryKeyRelatedField(
        queryset=ProductVersion.objects.all(), write_only=True, required=True
    )
    changes = serializers.CharField(write_only=True, required=False, allow_blank=True, default="Initial version")
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        help_text="List of Tag UUIDs to attach to this article."
    )

    class Meta:
        model = Articles
        fields = [
            'id', 'title', 'description', 'category', 'visibility', 
            'status', 'content', 'product_version', 'changes', 'tag_ids',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None

        if user and not user.is_superuser:
            requested_status = attrs.get('status', 'DRAFT')
            if requested_status not in ['DRAFT', 'REVIEW']:
                attrs['status'] = 'DRAFT'
        return attrs

    def create(self, validated_data):
        content = validated_data.pop('content')
        product_version = validated_data.pop('product_version')
        changes = validated_data.pop('changes', '')
        tag_ids = validated_data.pop('tag_ids', [])
        user = self.context['request'].user

        article = Articles.objects.create(**validated_data)

        for tag_id in tag_ids:
            ArticleTag.objects.get_or_create(article=article, tag_id=tag_id)

        ArticlesVersion.objects.create(
            article=article,
            product_version=product_version,
            content=content,
            changes=changes,
            status=article.status,
            author=user
        )
        return article

    def update(self, instance, validated_data):
        content = validated_data.pop('content', None)
        product_version = validated_data.pop('product_version', None)
        changes = validated_data.pop('changes', 'Updated article content')
        tag_ids = validated_data.pop('tag_ids', None)
        user = self.context['request'].user

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tag_ids is not None:
            instance.article_tags.all().delete()
            for tag_id in tag_ids:
                ArticleTag.objects.get_or_create(article=instance, tag_id=tag_id)
        
        if content or product_version:
            latest_version = instance.versions.order_by('-created_at').first()
            ArticlesVersion.objects.create(
                article=instance,
                product_version=product_version or latest_version.product_version,
                content=content or latest_version.content,
                changes=changes,
                status=instance.status,
                author=user
            )
        return instance


class ArticleDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    article_tags = ArticleTagSerializer(many=True, read_only=True)
    versions = ArticlesVersionSerializer(many=True, read_only=True)
    images = ArticleImageSerializer(many=True, read_only=True)

    class Meta:
        model = Articles
        fields = [
            'id', 'title', 'description', 'category', 'visibility', 
            'status', 'article_tags', 'versions', 'images', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']