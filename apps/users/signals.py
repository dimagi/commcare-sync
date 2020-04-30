from allauth.account.signals import user_signed_up
from django.conf import settings
from django.core.mail import mail_admins
from django.dispatch import receiver


@receiver(user_signed_up)
def handle_sign_up(request, user, **kwargs):
    # customize this function to do custom logic on sign up, e.g. send a welcome email
    # or subscribe them to your mailing list.
    # This example notifies the admins, in case you want to keep track of sign ups
    _notify_admins_of_signup(user)
    # and subscribes them to a mailchimp mailing list
    _subscribe_to_mailing_list(user)


def _notify_admins_of_signup(user):
    mail_admins(
        "Yowsers, someone signed up for the site!",
        "Email: {}".format(user.email)
    )


def _subscribe_to_mailing_list(user):
    # todo: better handle all of this or remove it
    try:
        from mailchimp3 import MailChimp
        from mailchimp3.mailchimpclient import MailChimpError
    except ImportError:
        return

    if getattr(settings, 'MAILCHIMP_API_KEY', None) and getattr(settings, 'MAILCHIMP_LIST_ID', None):
        client = MailChimp(mc_api=settings.MAILCHIMP_API_KEY)
        try:
            client.lists.members.create(settings.MAILCHIMP_LIST_ID, {
                'email_address': user.email,
                'status': 'subscribed',
            })
        except MailChimpError as e:
            # likely it's just that they were already subscribed so don't worry about it
            try:
                # but do log to sentry if available
                from sentry_sdk import capture_exception
                capture_exception(e)
            except ImportError:
                pass
