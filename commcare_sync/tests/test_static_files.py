from django.test import Client, override_settings


@override_settings(WHITENOISE_USE_FINDERS=True)
def test_static_files_are_served_by_the_app():
    response = Client().get('/static/css/site.css')
    assert response.status_code == 200
    assert response['Content-Type'].startswith('text/css')
