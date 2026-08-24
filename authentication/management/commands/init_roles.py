from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from authentication.models import Role

User = get_user_model()


class Command(BaseCommand):
    help = "Creates the initial Administrator role with full control permissions (*), and optionally assigns it to a user."

    def add_arguments(self, parser):
        parser.add_argument(
            '--name',
            type=str,
            default='Administrator',
            help='Name of the full control role (default: "Administrator").'
        )
        parser.add_argument(
            '--assign-to',
            type=str,
            help='Email of a user to assign this Administrator role to.',
            default=None
        )

    def handle(self, *args, **options):
        role_name = options['name'].strip()
        assign_email = options['assign_to']

        # Collect all system permission codes
        all_permissions = ["*"]
        categories = Role.get_available_permissions()
        for cat in categories:
            for perm in cat.get('permissions', []):
                all_permissions.append(perm['code'])

        # Remove duplicates while preserving wildcard first
        all_permissions = list(dict.fromkeys(all_permissions))

        role, created = Role.objects.get_or_create(
            name=role_name,
            defaults={
                'description': 'Full Control Administrator with unrestricted access to all application features.',
                'permissions': all_permissions
            }
        )

        if not created:
            role.permissions = all_permissions
            if not role.description:
                role.description = 'Full Control Administrator with unrestricted access to all application features.'
            role.save()
            self.stdout.write(
                self.style.SUCCESS(f"Updated existing role '{role_name}' with full control permissions.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully created initial full-control role '{role_name}'.")
            )

        if assign_email:
            email = assign_email.strip().lower()
            try:
                user = User.objects.get(email=email)
                user.role = role
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f"Assigned role '{role_name}' to user '{email}'.")
                )
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"User '{email}' does not exist. Role created but not assigned.")
                )

