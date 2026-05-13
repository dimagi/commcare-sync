import hashlib

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.urls import reverse


class CustomUserManager(UserManager):

    def get_by_natural_key(self, username):
        # USERNAME_FIELD is 'email'; emails are stored lowercased on save,
        # but lookups should still be case-insensitive to tolerate any
        # legacy or admin-created mixed-case rows.
        return self.get(**{f'{self.model.USERNAME_FIELD}__iexact': username})


class CustomUser(AbstractUser):
    """
    Add additional fields to the user model here.
    """
    """
    Abstract base class for users, with a small amount of added functionality
    """
    email = models.EmailField(unique=True)
    avatar = models.FileField(upload_to='profile-pictures/', null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email

    def get_display_name(self):
        if self.get_full_name().strip():
            return self.get_full_name()
        return self.email

    @property
    def is_admin(self):
        """An admin user is_active, is_superuser, and is_staff."""
        return self.is_active and self.is_superuser and self.is_staff

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
