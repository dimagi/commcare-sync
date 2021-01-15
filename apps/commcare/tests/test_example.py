from django.conf import settings
from django.test import SimpleTestCase, TestCase

from apps.commcare.models import CommCareServer


class ExampleTest(SimpleTestCase):

    def test_success(self):
        self.assertEqual(1, 1)


class ExampleDbTest(TestCase):

    def test_default_hq_auto_created(self):
        server = CommCareServer.objects.get()
        self.assertEqual(server.name, 'CommCare HQ')
        self.assertEqual(server.url, settings.COMMCARE_DEFAULT_SERVER)
