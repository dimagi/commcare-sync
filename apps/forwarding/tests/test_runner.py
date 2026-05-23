from unittest.mock import patch

from unmagic import fixture, use

from tests.fixtures import database

from ..models import ForwardingConfig, ForwardingDestination, ForwardingRun
from ..runner import run_forwarding


@fixture
@use('db')
def put_destination():
    yield ForwardingDestination.objects.create(
        name='PUT Lookup Table',
        api_url='https://example.com/api/lookup_table/abc/',
        method=ForwardingDestination.HttpMethod.PUT,
    )


@use('db', database)
class TestRunForwarding:

    @use(put_destination)
    def test_method_passed_to_forwarder(self):
        cfg = ForwardingConfig.objects.create(
            name='Lookup Table Refresh',
            database=database(),
            destination=put_destination(),
            query="SELECT '{\"rows\": []}'",
        )
        fwd_run = ForwardingRun.objects.create(forwarding_config=cfg)
        with (
            patch('apps.forwarding.runner.execute_query') as exec_q,
            patch('apps.forwarding.runner.forward_to_api') as fwd
        ):
            exec_q.return_value = '{"rows": []}'
            fwd.return_value.status_code = 200

            run_forwarding(fwd_run)

        fwd.assert_called_once()
        args, kwargs = fwd.call_args
        # api_url, payload & credentials are args; method is kwarg
        assert kwargs.get('method') == 'PUT'

    def test_method_defaults_to_post(self):
        dest = ForwardingDestination.objects.create(
            name='POST Endpoint',
            api_url='https://example.com/api',
        )
        cfg = ForwardingConfig.objects.create(
            name='Plain Forwarder',
            database=database(),
            destination=dest,
            query="SELECT '{}'",
        )
        fwd_run = ForwardingRun.objects.create(forwarding_config=cfg)
        with (
            patch('apps.forwarding.runner.execute_query') as exec_q,
            patch('apps.forwarding.runner.forward_to_api') as fwd
        ):
            exec_q.return_value = '{}'
            fwd.return_value.status_code = 200

            run_forwarding(fwd_run)

        args, kwargs = fwd.call_args
        assert kwargs.get('method') == 'POST'
