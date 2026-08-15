from unittest.mock import patch

from django.test import TestCase

from articles.models import Articles, ArticlesVersion, Category
from authentication.models import User
from product.models import Product, ProductVersion
from .services import ChatbotService


class ChatbotGroundedAnswerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='admin@example.com',
            password='StrongPass123!',
            first_name='System',
            last_name='Admin',
            is_staff=True,
            is_superuser=True,
        )
        self.product = Product.objects.create(
            name='HMIS',
            description='Health Management Information System',
            api_key='prod-key',
            api_secret='prod-secret',
            github_url='https://github.com/example/hmis',
        )
        self.category = Category.objects.create(name='General', description='General docs')

        self.version = ProductVersion.objects.create(
            product=self.product,
            version='1.0.0',
            description='Added patient registration workflow.',
            status='approved',
        )

        self.article = Articles.objects.create(
            title='Patient Registration',
            description='How patient registration works in HMIS.',
            category=self.category,
            visibility='PUBLIC',
            status='PUBLISHED',
        )
        self.article_version = ArticlesVersion.objects.create(
            article=self.article,
            product_version=self.version,
            content='Patients can register by entering their ID number, selecting the clinic, and confirming the appointment before saving.',
            status='PUBLISHED',
            author=self.user,
            embedding=[0.1] * 1536,
        )

    def test_retrieve_relevant_knowledge_filters_by_product_and_returns_best_article(self):
        context, article_ids = ChatbotService.retrieve_relevant_knowledge(
            'How do patients register for care?',
            product_id=str(self.product.id),
            limit=5,
        )

        self.assertIn('Patient Registration', context)
        self.assertIn(str(self.article.id), [str(article_id) for article_id in article_ids])

    @patch('chat.services.ChatbotService._chat_completion_with_backoff')
    def test_generate_ai_response_uses_article_context_as_ground_truth(self, mock_completion):
        mock_completion.return_value = type(
            'Response',
            (),
            {'choices': [type('Choice', (), {'message': type('Message', (), {'content': 'Patients register by entering their ID number and confirming the appointment before saving.'})()})()]}
        )

        response = ChatbotService.generate_ai_response(
            question='How do patients register for care?',
            context='Title: Patient Registration\nContent: Patients can register by entering their ID number, selecting the clinic, and confirming the appointment before saving.',
            product_id=str(self.product.id),
        )

        self.assertIn('ID number', response)
        self.assertIn('confirming the appointment', response.lower())
        self.assertNotIn('I do not have enough information', response)
