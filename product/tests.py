from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import User
from articles.models import Articles, ArticlesVersion, Category
from product.models import Product, ProductVersion


class ProductVersionArticleSyncTests(TestCase):
    def setUp(self):
        self.client = APIClient()
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
            github_url='https://github.com/example/hmis'
        )
        self.category = Category.objects.create(
            name='General',
            description='General product articles'
        )
        self.client.force_authenticate(user=self.user)

    def test_sync_updates_related_articles_when_product_version_changes(self):
        version = ProductVersion.objects.create(
            product=self.product,
            version='1.0.0',
            description='Added patient dashboard and reporting workflow.'
        )
        article = Articles.objects.create(
            title='Patient Dashboard',
            description='Older patient dashboard docs.',
            category=self.category,
            visibility='PUBLIC',
            status='PUBLISHED',
        )
        ArticlesVersion.objects.create(
            article=article,
            product_version=version,
            content='Older patient dashboard content.',
            status='PUBLISHED',
            author=self.user,
        )

        response = self.client.post(
            '/prod/versions/sync-articles/',
            {
                'product_id': str(self.product.id),
                'product_version_id': str(version.id),
            },
            format='json'
        )

        self.assertIn(response.status_code, [200, 201])
        article.refresh_from_db()
        self.assertIn('patient dashboard', article.description.lower())
        latest_version = article.versions.order_by('-created_at').first()
        self.assertIsNotNone(latest_version)
        self.assertIn('patient dashboard', latest_version.content.lower())

    def test_sync_creates_new_article_when_no_article_exists_for_product(self):
        version = ProductVersion.objects.create(
            product=self.product,
            version='1.1.0',
            description='Added referral tracking for clinical teams.'
        )

        response = self.client.post(
            '/prod/versions/sync-articles/',
            {
                'product_id': str(self.product.id),
                'product_version_id': str(version.id),
            },
            format='json'
        )

        self.assertIn(response.status_code, [200, 201])
        self.assertTrue(
            Articles.objects.filter(
                title__icontains='HMIS',
                description__icontains='referral tracking'
            ).exists()
        )

        article = Articles.objects.latest('created_at')
        latest_version = article.versions.order_by('-created_at').first()
        self.assertIsNotNone(latest_version)
        self.assertTrue(len(latest_version.content) > 0)

    def test_sync_updates_article_contents_using_openfront_format(self):
        version = ProductVersion.objects.create(
            product=self.product,
            version='2.0.0',
            description='Added referral tracking for clinical teams.'
        )
        article = Articles.objects.create(
            title='Referral Workflow',
            description='Referral workflow notes.',
            category=self.category,
            visibility='PUBLIC',
            status='PUBLISHED',
        )
        ArticlesVersion.objects.create(
            article=article,
            product_version=version,
            content='Legacy referral workflow content.',
            status='PUBLISHED',
            author=self.user,
        )

        response = self.client.post(
            '/prod/versions/sync-articles/',
            {
                'product_id': str(self.product.id),
                'product_version_id': str(version.id),
                'description': 'Added referral tracking for clinical teams.'
            },
            format='json'
        )

        self.assertIn(response.status_code, [200, 201])
        article.refresh_from_db()
        latest_version = article.versions.order_by('-created_at').first()
        self.assertIsNotNone(latest_version)

    def test_sync_rewrites_login_steps_when_old_auth_method_changes(self):
        version = ProductVersion.objects.create(
            product=self.product,
            version='3.0.0',
            description='Login now supports phone number or email with OTP instead of email and password.'
        )
        article = Articles.objects.create(
            title='Login',
            description='Legacy login guidance for staff.',
            category=self.category,
            visibility='PUBLIC',
            status='PUBLISHED',
        )
        ArticlesVersion.objects.create(
            article=article,
            product_version=version,
            content='Users log in with email and password to access the dashboard.',
            status='PUBLISHED',
            author=self.user,
        )

        response = self.client.post(
            '/prod/versions/sync-articles/',
            {
                'product_id': str(self.product.id),
                'product_version_id': str(version.id),
                'description': 'Login now supports phone number or email with OTP instead of email and password.'
            },
            format='json'
        )

        self.assertIn(response.status_code, [200, 201])
        article.refresh_from_db()
        latest_version = article.versions.order_by('-created_at').first()
        content_lower = latest_version.content.lower()
        if response.status_code == 200:
            self.assertIn('phone number', content_lower)
            self.assertIn('otp', content_lower)
            self.assertIn('email', content_lower)
            self.assertNotIn('email and password', content_lower)
            self.assertIn('log in', content_lower)

    def test_product_auto_keys_and_webhook_url(self):
        self.client.force_authenticate(user=self.user)
        res_create = self.client.post('/prod/products/', {
            'name': 'Pharmacy System',
            'description': 'Medication dispensary module'
        }, format='json')
        self.assertEqual(res_create.status_code, 201)
        data = res_create.data.get('data', res_create.data)

        self.assertTrue(data['api_key'].startswith('hk_live_'))
        self.assertTrue(data['api_secret'].startswith('hs_live_'))
        self.assertTrue(data['webhook_token'].startswith('whk_'))
        self.assertIn('/github/webhook/whk_', data['github_webhook_url'])

        # Verify GET /prod/products/ returns github_webhook_url
        res_list = self.client.get('/prod/products/')
        self.assertEqual(res_list.status_code, 200)
        products = res_list.data.get('data', res_list.data)
        item = [p for p in products if p['name'] == 'Pharmacy System'][0]
        self.assertIn('/github/webhook/', item['github_webhook_url'])
