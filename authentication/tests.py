from django.test import TestCase
from django.core import mail
from rest_framework.test import APIClient
from rest_framework import status

from .models import Role, User


class StaffCreationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPassword123!',
            first_name='Admin',
            last_name='User'
        )
        self.client.force_authenticate(user=self.admin)
        self.role = Role.objects.create(
            name='Senior Nurse',
            description='Medical staff member',
            permissions=['articles:read', 'articles:create']
        )

    def test_create_staff_user_hashes_password_and_sets_staff_flag(self):
        user = User.objects.create_user(
            email='staff@example.com',
            password='StrongPass123!',
            first_name='Jane',
            last_name='Doe',
            role=self.role,
            is_staff=True,
        )

        self.assertTrue(user.is_staff)
        self.assertNotEqual(user.password, 'StrongPass123!')
        self.assertTrue(user.check_password('StrongPass123!'))
        self.assertEqual(user.role, self.role)

    def test_role_creation_and_permissions(self):
        response = self.client.post('/auth/roles/', {
            'name': 'Content Editor',
            'description': 'Can edit articles and view dashboard',
            'permissions': ['articles:read', 'articles:update', 'dashboard:view']
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        role = Role.objects.get(name='Content Editor')
        self.assertEqual(role.permissions, ['articles:read', 'articles:update', 'dashboard:view'])

    def test_get_available_permissions(self):
        response = self.client.get('/auth/roles/available-permissions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        categories = [item['category'] for item in response.data['data']]
        self.assertIn('Articles', categories)
        self.assertIn('Staff & Roles', categories)

    def test_staff_creation_sends_email_with_password(self):
        mail.outbox = []
        payload = {
            'email': 'newstaff@example.com',
            'password': 'StaffSecretPass123!',
            'first_name': 'Alice',
            'last_name': 'Smith',
            'role': str(self.role.id)
        }

        response = self.client.post('/auth/staff/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check outbox email
        self.assertEqual(len(mail.outbox), 1)
        sent_mail = mail.outbox[0]
        self.assertEqual(sent_mail.to, ['newstaff@example.com'])
        self.assertIn('Welcome to HIMS', sent_mail.subject)
        self.assertIn('StaffSecretPass123!', sent_mail.body)
        # Check styled HTML alternative
        self.assertTrue(len(sent_mail.alternatives) > 0)
        html_content = sent_mail.alternatives[0][0]
        self.assertIn('#0f172a', html_content)  # slate-900
        self.assertIn('#b45309', html_content)  # amber-700

    def test_staff_password_update_sends_email(self):
        staff_user = User.objects.create_user(
            email='updatestaff@example.com',
            password='InitialPassword123!',
            first_name='Bob',
            last_name='Builder',
            is_staff=True
        )
        mail.outbox = []

        response = self.client.patch(f'/auth/staff/{staff_user.id}/', {
            'password': 'NewAdminUpdatedPass456!'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        staff_user.refresh_from_db()
        self.assertTrue(staff_user.check_password('NewAdminUpdatedPass456!'))

        self.assertEqual(len(mail.outbox), 1)
        sent_mail = mail.outbox[0]
        self.assertEqual(sent_mail.to, ['updatestaff@example.com'])
        self.assertIn('Password Has Been Updated', sent_mail.subject)
        self.assertIn('NewAdminUpdatedPass456!', sent_mail.body)

    def test_staff_dismissal_sends_email(self):
        staff_user = User.objects.create_user(
            email='dismissedstaff@example.com',
            password='Password123!',
            first_name='Charlie',
            last_name='Brown',
            is_staff=True,
            is_active=True
        )
        mail.outbox = []

        # Deactivate staff user
        response = self.client.patch(f'/auth/staff/{staff_user.id}/', {
            'is_active': False
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        staff_user.refresh_from_db()
        self.assertFalse(staff_user.is_active)

        self.assertEqual(len(mail.outbox), 1)
        sent_mail = mail.outbox[0]
        self.assertEqual(sent_mail.to, ['dismissedstaff@example.com'])
        self.assertIn('Account Deactivated', sent_mail.subject)

    def test_make_superuser_command(self):
        from django.core.management import call_command
        # Test promoting existing user
        regular_user = User.objects.create_user(
            email='regular@example.com',
            password='Password123!',
            first_name='Regular',
            last_name='User'
        )
        self.assertFalse(regular_user.is_superuser)

        call_command('make_superuser', 'regular@example.com')
        regular_user.refresh_from_db()
        self.assertTrue(regular_user.is_superuser)
        self.assertTrue(regular_user.is_staff)

        # Test creating new superuser via command
        call_command('make_superuser', 'brandnewadmin@example.com', password='CustomPassword123!')
        new_admin = User.objects.get(email='brandnewadmin@example.com')
        self.assertTrue(new_admin.is_superuser)
        self.assertTrue(new_admin.check_password('CustomPassword123!'))

    def test_init_roles_command(self):
        from django.core.management import call_command
        target_user = User.objects.create_user(
            email='target@example.com',
            password='Password123!',
            first_name='Target',
            last_name='User'
        )

        call_command('init_roles', '--assign-to', 'target@example.com')
        role = Role.objects.get(name='Administrator')
        self.assertIn('*', role.permissions)
        self.assertIn('articles:read', role.permissions)
        self.assertIn('staff:manage', role.permissions)

        target_user.refresh_from_db()
        self.assertEqual(target_user.role, role)
