from django.test import TestCase

from .models import Role, User


class StaffCreationTests(TestCase):
    def test_create_staff_user_hashes_password_and_sets_staff_flag(self):
        role = Role.objects.create(name='Senior Nurse')

        user = User.objects.create_user(
            email='staff@example.com',
            password='StrongPass123!',
            first_name='Jane',
            last_name='Doe',
            role=role,
            is_staff=True,
        )

        self.assertTrue(user.is_staff)
        self.assertNotEqual(user.password, 'StrongPass123!')
        self.assertTrue(user.check_password('StrongPass123!'))
        self.assertEqual(user.role, role)
