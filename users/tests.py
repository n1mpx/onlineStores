from django.test import TestCase
import requests
from django.conf import settings
from django.urls import reverse


class AuthAPITestCase(TestCase):

    def setUp(self):
        self.base_url = "http://127.0.0.1:8000/api/v1/auth"

    def test_login_view(self):
        url = reverse('login')
        data = {'email': 'test@example.com'}
        response = self.client.post(url, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('message', response.json())

    def test_confirm_view(self):
        url = f"{self.base_url}/confirm/"
        data = {
            "email": "user@example.com",
            "code": "123456"
        }

        response = requests.post(url, json=data)

        if response.status_code == 200:
            self.assertIn("access", response.json())
            self.assertIn("refresh", response.json())
        else:
            self.assertIn("error", response.json())

