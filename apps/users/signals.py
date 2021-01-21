from allauth.account.signals import user_signed_up
from django.core.mail import mail_admins
from django.dispatch import receiver


@receiver(user_signed_up)
def handle_sign_up(request, user, **kwargs):
    # customize this function to do custom logic on sign up, e.g. send a welcome email
    # or subscribe them to your mailing list.
    # This example notifies the admins, in case you want to keep track of sign ups
    _notify_admins_of_signup(user)


def _notify_admins_of_signup(user):
    mail_admins(
        "Yowsers, someone signed up for the site!",
        "Email: {}".format(user.email)
    )
