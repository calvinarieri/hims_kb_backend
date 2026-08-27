import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    permissions = models.JSONField(default=None, null=True, blank=True, help_text="List of feature permission strings enabled for this role.")

    def __str__(self):
        return self.name

    @classmethod
    def get_available_permissions(cls):
        """
        Returns all system feature permissions organized by feature category.
        """
        return [
            {
                "category": "Articles",
                "permissions": [
                    {"code": "articles:read", "label": "View Articles"},
                    {"code": "articles:create", "label": "Create Articles"},
                    {"code": "articles:update", "label": "Update Articles"},
                    {"code": "articles:delete", "label": "Delete Articles"},
                    {"code": "articles:approve", "label": "Approve Articles for Publication"},
                ]
            },
            {
                "category": "Staff & Roles",
                "permissions": [
                    {"code": "staff:read", "label": "View Staff Members"},
                    {"code": "staff:manage", "label": "Manage Staff (Create, Edit, Dismiss)"},
                    {"code": "roles:manage", "label": "Manage Roles & Permissions"},
                ]
            },
            {
                "category": "Support & Feedback",
                "permissions": [
                    {"code": "chat:manage", "label": "Manage Chat & Customer Service"},
                    {"code": "feedback:manage", "label": "View & Manage User Feedback"},
                ]
            },
            {
                "category": "Products",
                "permissions": [
                    {"code": "product:manage", "label": "Manage Products & Versions"},
                ]
            },
            {
                "category": "Dashboard",
                "permissions": [
                    {"code": "dashboard:view", "label": "View Analytics & Dashboard"},
                ]
            }
        ]



class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError("The Email field must be set")
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Creates and saves a superuser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['password','last_name', 'first_name']

    def __str__(self):
        return self.email
    


