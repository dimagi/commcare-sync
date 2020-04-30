from django.db import models


class PegasusBaseModel(models.Model):
    """
    Base model that includes default created / updated timestamps.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
