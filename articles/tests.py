from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from authentication.models import User, Role
from articles.models import Articles, ArticlesVersion, Category
from product.models import Product, ProductVersion
from chat.services import ChatbotService


class ArticlePermissionsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Super Admin
        self.super_admin = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPassword123!',
            first_name='Super',
            last_name='Admin'
        )

        # Roles
        self.author_role = Role.objects.create(
            name='Author Staff',
            permissions=['articles:read', 'articles:create', 'articles:update', 'articles:delete']
        )
        self.approver_role = Role.objects.create(
            name='Approver Staff',
            permissions=['articles:read', 'articles:approve']
        )

        # Staff Members
        self.staff_author1 = User.objects.create_user(
            email='author1@example.com',
            password='Password123!',
            first_name='Author',
            last_name='One',
            is_staff=True,
            role=self.author_role
        )
        self.staff_author2 = User.objects.create_user(
            email='author2@example.com',
            password='Password123!',
            first_name='Author',
            last_name='Two',
            is_staff=True,
            role=self.author_role
        )
        self.staff_approver = User.objects.create_user(
            email='approver@example.com',
            password='Password123!',
            first_name='Approver',
            last_name='User',
            is_staff=True,
            role=self.approver_role
        )

        # Shared Product & Category setup
        self.category = Category.objects.create(name='General Clinical', description='General docs')
        self.product = Product.objects.create(name='EHR Core', description='Core System', api_key='ehr_core_key')
        self.product_version = ProductVersion.objects.create(product=self.product, version='v1.0.0')

        # Articles
        self.pub_public_article = Articles.objects.create(
            title='Public Published Article',
            description='Public and published docs',
            category=self.category,
            visibility='PUBLIC',
            status='PUBLISHED'
        )
        self.pub_public_version = ArticlesVersion.objects.create(
            article=self.pub_public_article,
            product_version=self.product_version,
            content='Public published content for patient care.',
            status='PUBLISHED',
            author=self.staff_author1
        )

        self.priv_draft_article = Articles.objects.create(
            title='Private Draft Article',
            description='Private draft internal docs',
            category=self.category,
            visibility='PRIVATE',
            status='DRAFT'
        )
        self.priv_draft_version = ArticlesVersion.objects.create(
            article=self.priv_draft_article,
            product_version=self.product_version,
            content='Internal sensitive draft content.',
            status='DRAFT',
            author=self.staff_author1
        )

        self.pub_draft_article = Articles.objects.create(
            title='Public Draft Article',
            description='Public draft docs',
            category=self.category,
            visibility='PUBLIC',
            status='DRAFT'
        )
        self.pub_draft_version = ArticlesVersion.objects.create(
            article=self.pub_draft_article,
            product_version=self.product_version,
            content='Public draft content waiting for review.',
            status='DRAFT',
            author=self.staff_author2
        )

    def test_unauthenticated_user_only_sees_public_published_articles(self):
        self.client.logout()
        # List endpoint
        response = self.client.get('/docs/articles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        titles = [a['title'] for a in response.data]
        self.assertIn('Public Published Article', titles)
        self.assertNotIn('Private Draft Article', titles)
        self.assertNotIn('Public Draft Article', titles)

        # Retrieve single PUBLIC + PUBLISHED article (should succeed with 200 OK)
        res_pub = self.client.get(f'/docs/articles/{self.pub_public_article.id}/')
        self.assertEqual(res_pub.status_code, status.HTTP_200_OK)
        self.assertEqual(res_pub.data['title'], 'Public Published Article')

        # Retrieve single PRIVATE or DRAFT article (should fail with 404 Not Found)
        res_priv = self.client.get(f'/docs/articles/{self.priv_draft_article.id}/')
        self.assertEqual(res_priv.status_code, status.HTTP_404_NOT_FOUND)

    def test_staff_can_view_public_and_private_articles(self):
        self.client.force_authenticate(user=self.staff_author1)
        response = self.client.get('/docs/articles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        titles = [a['title'] for a in response.data]
        self.assertIn('Public Published Article', titles)
        self.assertIn('Private Draft Article', titles)
        self.assertIn('Public Draft Article', titles)

    def test_staff_can_update_only_authored_articles(self):
        # Author 1 updates their own article (pub_public_article authored by author1)
        self.client.force_authenticate(user=self.staff_author1)
        res_own = self.client.patch(f'/docs/articles/{self.pub_public_article.id}/', {
            'description': 'Updated by Author 1'
        }, format='json')
        self.assertEqual(res_own.status_code, status.HTTP_200_OK)

        # Author 1 attempts to update Author 2's article (pub_draft_article authored by author2)
        res_other = self.client.patch(f'/docs/articles/{self.pub_draft_article.id}/', {
            'description': 'Attempted update by Author 1'
        }, format='json')
        self.assertEqual(res_other.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_delete_only_authored_articles(self):
        # Author 1 attempts to delete Author 2's article
        self.client.force_authenticate(user=self.staff_author1)
        res_other = self.client.delete(f'/docs/articles/{self.pub_draft_article.id}/')
        self.assertEqual(res_other.status_code, status.HTTP_403_FORBIDDEN)

        # Author 1 deletes their own article
        res_own = self.client.delete(f'/docs/articles/{self.pub_public_article.id}/')
        self.assertEqual(res_own.status_code, status.HTTP_204_NO_CONTENT)

    def test_super_admin_has_full_crud_and_approval_access(self):
        self.client.force_authenticate(user=self.super_admin)

        # Super admin can update ANY article (even authored by staff)
        res_update = self.client.patch(f'/docs/articles/{self.pub_draft_article.id}/', {
            'description': 'Super admin update'
        }, format='json')
        self.assertEqual(res_update.status_code, status.HTTP_200_OK)

        # Super admin can approve article
        res_approve = self.client.post(f'/docs/articles/{self.pub_draft_article.id}/approve/')
        self.assertEqual(res_approve.status_code, status.HTTP_200_OK)

        self.pub_draft_article.refresh_from_db()
        self.assertEqual(self.pub_draft_article.status, 'PUBLISHED')

    def test_article_saved_as_draft_until_released_for_approval(self):
        from articles.models import Tag
        tag1 = Tag.objects.create(name='Clinical')
        tag2 = Tag.objects.create(name='Emergency')

        # 1. Author creates a new article with 1 tag
        self.client.force_authenticate(user=self.staff_author1)
        res_create = self.client.post('/docs/articles/', {
            'title': 'New Medical Protocol',
            'description': 'Draft protocol info',
            'category': str(self.category.id),
            'visibility': 'PUBLIC',
            'status': 'DRAFT',
            'content': 'Medical protocol content text.',
            'product_version': str(self.product_version.id),
            'tag_ids': [str(tag1.id)]
        }, format='json')
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        article_id = res_create.data['id']

        created_article = Articles.objects.get(id=article_id)
        self.assertEqual(created_article.status, 'DRAFT')

        # 2. Author attempts to submit for review with only 1 tag (should fail with 400 Bad Request)
        res_fail_submit = self.client.post(f'/docs/articles/{article_id}/submit-for-review/')
        self.assertEqual(res_fail_submit.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('at least 2 tags', res_fail_submit.data['detail'])

        # Add 2nd tag to article
        self.client.patch(f'/docs/articles/{article_id}/', {
            'tag_ids': [str(tag1.id), str(tag2.id)]
        }, format='json')

        # 3. Author submits the article for approval with 2 tags (should succeed)
        res_submit = self.client.post(f'/docs/articles/{article_id}/submit-for-review/')
        self.assertEqual(res_submit.status_code, status.HTTP_200_OK)

        created_article.refresh_from_db()
        self.assertEqual(created_article.status, 'REVIEW')

        # 4. Approver staff approves the article for publication
        self.client.force_authenticate(user=self.staff_approver)
        res_approve = self.client.post(f'/docs/articles/{article_id}/approve/')
        self.assertEqual(res_approve.status_code, status.HTTP_200_OK)

        created_article.refresh_from_db()
        self.assertEqual(created_article.status, 'PUBLISHED')

    def test_staff_approval_permission_enforcement(self):
        # Author 1 (without articles:approve) attempts to approve an article
        self.client.force_authenticate(user=self.staff_author1)
        res_author = self.client.post(f'/docs/articles/{self.pub_draft_article.id}/approve/')
        self.assertEqual(res_author.status_code, status.HTTP_403_FORBIDDEN)

        # Approver staff (with articles:approve) approves article
        self.client.force_authenticate(user=self.staff_approver)
        res_approver = self.client.post(f'/docs/articles/{self.pub_draft_article.id}/approve/')
        self.assertEqual(res_approver.status_code, status.HTTP_200_OK)

    def test_chatbot_retrieval_only_retrieves_public_and_published_articles(self):
        from unittest.mock import patch
        self.pub_public_version.embedding = [0.1] * 1536
        self.pub_public_version.save()
        self.priv_draft_version.embedding = [0.1] * 1536
        self.priv_draft_version.save()
        self.pub_draft_version.embedding = [0.1] * 1536
        self.pub_draft_version.save()

        with patch.object(ChatbotService, 'generate_article_embedding'), patch.object(ChatbotService, '_create_embedding_with_backoff', return_value=[0.1]*1536):
            context_str, article_ids = ChatbotService.retrieve_relevant_knowledge(
                query='patient care sensitive draft',
                product_id=str(self.product.id)
            )

        # Should retrieve public_published_article but NEVER private or draft articles
        self.assertIn(self.pub_public_article.id, article_ids)
        self.assertNotIn(self.priv_draft_article.id, article_ids)
        self.assertNotIn(self.pub_draft_article.id, article_ids)
