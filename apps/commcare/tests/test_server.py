from django.conf import settings
from django.test import SimpleTestCase, TestCase

from apps.commcare.models import CommCareServer


class ServerTest(SimpleTestCase):

    def test_get_url_base_no_slash(self):
        self.assertEqual('https://www.commcarehq.org', CommCareServer(url='https://www.commcarehq.org').get_url_base())

    def test_get_url_base_with_slash(self):
        self.assertEqual('https://www.commcarehq.org', CommCareServer(url='https://www.commcarehq.org/').get_url_base())


class ServerDbTest(TestCase):

    def test_default_hq_auto_created(self):
        server = CommCareServer.objects.get()
        self.assertEqual(server.name, 'CommCare HQ')
        self.assertEqual(server.url, settings.COMMCARE_DEFAULT_SERVER)
