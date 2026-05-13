import hashlib

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.urls import reverse


class CustomUserManager(BaseUserManager):

    def get_by_natural_key(self, username):
        # Required for case-insensitive login: Django's auth backend passes the
        # raw user-supplied email to this method, which by default does an
        # exact match. Stored emails are always lowercase (see save()), so
        # __iexact lets users log in with any casing.
        return self.get(**{f'{self.model.USERNAME_FIELD}__iexact': username})

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required.')
        # CustomUser.save() lowercases email; normalize_email() handles the
        # domain portion for callers that bypass save() (rare).
        email = self.normalize_email(email)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, password, **extra_fields)

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
