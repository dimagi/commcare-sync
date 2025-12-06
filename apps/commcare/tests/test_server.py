from django.conf import settings
from django.test import SimpleTestCase, TestCase

from apps.commcare.models import CommCareServer


class ServerTest(SimpleTestCase):
    def test_get_url_base_no_slash(self):
        assert (
            CommCareServer(url='https://www.commcarehq.org').get_url_base()
            == 'https://www.commcarehq.org'
        )

    def test_get_url_base_with_slash(self):
        assert (
            CommCareServer(url='https://www.commcarehq.org/').get_url_base()
            == 'https://www.commcarehq.org'
        )


class ServerDbTest(TestCase):
    def test_default_hq_auto_created(self):
        server = CommCareServer.objects.get()
        assert server.name == 'CommCare HQ'
        assert server.url == settings.COMMCARE_DEFAULT_SERVER
