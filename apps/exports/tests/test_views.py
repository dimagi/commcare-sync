from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse


class StaffRequiredTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        UserModel = get_user_model()
        cls.normal_user = UserModel(username='user@example.com',
                                    email='user@example.com')
        cls.normal_user.set_password('Passw0rd!')
        cls.normal_user.save()
        cls.staff_user = UserModel(username='staff@example.com',
                                   email='staff@example.com',
                                   is_staff=True)
        cls.staff_user.set_password('Passw0rd!')
        cls.staff_user.save()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.staff_user.delete()
        cls.normal_user.delete()

    def test_not_logged_in(self):
        client = Client()
        response = client.get(reverse('exports:create_database'))
        self.assertEqual(response.status_code, 302)

    def test_normal_user(self):
        client = Client()
        client.login(username='user@example.com',
                     password='Passw0rd!')
        response = client.get(reverse('exports:create_database'))
        self.assertEqual(response.status_code, 403)

    def test_staff_user(self):
        client = Client()
        client.login(username='staff@example.com',
                     password='Passw0rd!')
        response = client.get(reverse('exports:create_database'))
        self.assertEqual(response.status_code, 200)
