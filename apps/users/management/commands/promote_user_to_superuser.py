from django.core.management.base import BaseCommand, CommandError

from apps.users.models import CustomUser


class Command(BaseCommand):
    help = 'Promotes the given user to a superuser and provides admin access.'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str)

    def handle(self, email, **options):
        try:
            user = CustomUser.objects.get(email=email.lower())
        except CustomUser.DoesNotExist:
            raise CommandError(f'No user with email {email} found!')
        user.is_superuser = True
        user.is_staff = True
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f'{user.email} successfully promoted to superuser and can now access the admin site'
        ))
