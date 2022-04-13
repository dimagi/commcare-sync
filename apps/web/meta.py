from django.contrib.sites.models import Site


def absolute_url(relative_url: str) -> str:
    return 'https://{}{}'.format(Site.objects.get_current().domain, relative_url)
