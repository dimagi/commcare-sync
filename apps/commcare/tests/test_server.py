from django.conf import settings
from django.test import SimpleTestCase
from unmagic import use

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


@use('db')
class TestCommCareServerDefaults:
    def test_default_hq_server_model_defaults(self):
        """CommCareServer defaults match the expected HQ server configuration.

        The data migration 0002_create_commcare_server calls
        CommCareServer.objects.get_or_create() with no arguments, relying on
        these model defaults to produce the correct server record.
        """
        server, _ = CommCareServer.objects.get_or_create()
        assert server.name == 'CommCare HQ'
        assert server.url == settings.COMMCARE_DEFAULT_SERVER
