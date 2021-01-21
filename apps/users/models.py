import hashlib

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse


class CustomUser(AbstractUser):
    """
    Add additional fields to the user model here.
    """
    """
    Abstract base class for users, with a small amount of added functionality
    """
    avatar = models.FileField(upload_to='profile-pictures/', null=True, blank=True)

    def __str__(self):
        return self.email

    def get_display_name(self):
        if self.get_full_name().strip():
            return self.get_full_name()
        return self.email

    @property
    def avatar_url(self):
        if self.avatar:
            return reverse('users:avatar', args=[self.id])
        else:
            return 'https://www.gravatar.com/avatar/{}?s=128&d=identicon'.format(self.gravatar_id)

    @property
    def gravatar_id(self):
        # https://en.gravatar.com/site/implement/hash/
        return hashlib.md5(self.email.lower().strip().encode('utf-8')).hexdigest()
