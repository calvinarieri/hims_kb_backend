from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from product.models import Product, ProductVersion


class GithubWebhookTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.product = Product.objects.create(
            name='EHR Core',
            description='Core EHR System'
        )

    def test_github_webhook_token_lookup_and_version_creation(self):
        webhook_url = f"/github/webhook/{self.product.webhook_token}/"

        # 1. Test ping event
        res_ping = self.client.post(
            webhook_url,
            {},
            HTTP_X_GITHUB_EVENT='ping',
            format='json'
        )
        self.assertEqual(res_ping.status_code, status.HTTP_200_OK)
        self.assertIn('Pong', res_ping.data['status'])

        # 2. Test pull request merge payload via token URL
        payload = {
            'action': 'closed',
            'test_mode': True,
            'description': 'Added patient vitals tracking widget',
            'pull_request': {
                'merged': True,
                'body': 'Added patient vitals tracking widget'
            },
            'code_changes': [
                {'filename': 'vitals.py', 'patch': '+ def track_vitals(): pass'}
            ]
        }

        res_webhook = self.client.post(
            webhook_url,
            payload,
            HTTP_X_GITHUB_EVENT='pull_request',
            format='json'
        )
        self.assertEqual(res_webhook.status_code, status.HTTP_200_OK)
        self.assertEqual(res_webhook.data['product'], 'EHR Core')

        # Verify ProductVersion created
        version = ProductVersion.objects.filter(product=self.product).latest('created_at')
        self.assertIsNotNone(version)
        self.assertIn('patient vitals tracking', version.description.lower())
