from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Promote an existing user to superuser or create a new superuser by email."

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='The email address of the user to make a superuser.')
        parser.add_argument(
            '--password',
            type=str,
            help='Password to set if a new superuser account is created, or to update existing password.',
            default=None
        )

    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        password = options['password']

        if not email:
            raise CommandError("Please provide a valid email address.")

        try:
            user = User.objects.get(email=email)
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            if password:
                user.set_password(password)
            user.save()

            self.stdout.write(
                self.style.SUCCESS(f"Successfully promoted existing user '{email}' to superuser.")
            )

        except User.DoesNotExist:
            if not password:
                password = 'SuperUser123!'
                self.stdout.write(
                    self.style.WARNING(f"No password specified. Using default password: {password}")
                )

            user = User.objects.create_superuser(
                email=email,
                password=password,
                first_name='Super',
                last_name='User'
            )

            self.stdout.write(
                self.style.SUCCESS(f"Successfully created new superuser '{email}'.")
            )

