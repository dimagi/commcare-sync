from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied


def staff_required(function=None, login_url=None, raise_exception=True):
    """
    Decorator for views that checks that the user is logged in and is
    marked as "staff"
    """
    def logged_in_and_staff(user):
        if not user.is_authenticated:
            return False  # Show the log-in form
        if user.is_staff:
            return True
        if raise_exception:
            raise PermissionDenied  # Call the 403 handler
        return False

    decorator = user_passes_test(
        logged_in_and_staff,
        login_url=login_url,
    )
    if function:
        return decorator(function)
    return decorator
