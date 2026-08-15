from rest_framework import serializers
from .models import ArticleFeedback


class ArticleFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleFeedback
        fields = ['id', 'article', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_rating(self, value):
        if value is None:
            return value
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value
