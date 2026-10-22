"""Tests for user registration (email and phone) and flexible login."""
import unittest
import uuid
from _isolation import TEMP_DIR
from fastapi.testclient import TestClient

from backend.main import app

HEADERS = {'X-Requested-With': 'so-thu-chi'}

class RegisterTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, headers=HEADERS)

    def test_register_with_email_success(self):
        email = f"user_{uuid.uuid4().hex[:8]}@example.com"
        r = self.client.post('/api/auth/register', json={
            'name': 'Nguyễn Văn A',
            'email': email,
            'password': 'password123',
            'shop_name': 'Tiệm Cà Phê Mộc'
        })
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data['name'], 'Nguyễn Văn A')
        self.assertEqual(data['email'], email)
        self.assertEqual(data['household'], 'Tiệm Cà Phê Mộc')

        # Test session cookie was set
        self.assertIn('sothuchi_session', self.client.cookies)

        # Test logging in with newly registered email
        new_client = TestClient(app, headers=HEADERS)
        login_res = new_client.post('/api/auth/login', json={
            'email': email,
            'password': 'password123'
        })
        self.assertEqual(login_res.status_code, 200)
        self.assertEqual(login_res.json()['email'], email)

    def test_register_with_phone_only_success(self):
        phone = f"09{uuid.uuid4().int % 100000000:08d}"
        r = self.client.post('/api/auth/register', json={
            'name': 'Trần Thị B',
            'phone': phone,
            'password': 'password456',
            'shop_name': 'Tiệm Tạp Hóa Cô B'
        })
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data['name'], 'Trần Thị B')
        self.assertEqual(data['phone'], phone)
        self.assertEqual(data['household'], 'Tiệm Tạp Hóa Cô B')

        # Test logging in with phone number directly
        new_client = TestClient(app, headers=HEADERS)
        login_res = new_client.post('/api/auth/login', json={
            'email': phone,
            'password': 'password456'
        })
        self.assertEqual(login_res.status_code, 200)
        self.assertEqual(login_res.json()['phone'], phone)

        # Test logging in with formatted phone number (spaces)
        formatted_phone = f"{phone[:4]} {phone[4:7]} {phone[7:]}"
        login_formatted = new_client.post('/api/auth/login', json={
            'email': formatted_phone,
            'password': 'password456'
        })
        self.assertEqual(login_formatted.status_code, 200)

    def test_register_with_both_email_and_phone(self):
        uid = uuid.uuid4().hex[:8]
        email = f"both_{uid}@example.com"
        phone = f"08{uuid.uuid4().int % 100000000:08d}"
        r = self.client.post('/api/auth/register', json={
            'name': 'Lê Văn C',
            'email': email,
            'phone': phone,
            'password': 'password789'
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['email'], email)
        self.assertEqual(data['phone'], phone)
        self.assertEqual(data['household'], 'Tiệm của Lê Văn C')

        # Login with email works
        client1 = TestClient(app, headers=HEADERS)
        r1 = client1.post('/api/auth/login', json={'email': email, 'password': 'password789'})
        self.assertEqual(r1.status_code, 200)

        # Login with phone works
        client2 = TestClient(app, headers=HEADERS)
        r2 = client2.post('/api/auth/login', json={'email': phone, 'password': 'password789'})
        self.assertEqual(r2.status_code, 200)

    def test_register_validations(self):
        # Missing both email and phone
        r = self.client.post('/api/auth/register', json={
            'name': 'Thiếu Thông Tin',
            'password': 'password123'
        })
        self.assertEqual(r.status_code, 422)

        # Short password
        r = self.client.post('/api/auth/register', json={
            'name': 'Mật Khẩu Ngắn',
            'email': 'short@example.com',
            'password': '123'
        })
        self.assertEqual(r.status_code, 422)

        # Invalid email format
        r = self.client.post('/api/auth/register', json={
            'name': 'Email Sai',
            'email': 'invalid-email',
            'password': 'password123'
        })
        self.assertEqual(r.status_code, 422)

        # Invalid phone format
        r = self.client.post('/api/auth/register', json={
            'name': 'SĐT Sai',
            'phone': '12345',
            'password': 'password123'
        })
        self.assertEqual(r.status_code, 422)

    def test_duplicate_rejection(self):
        email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
        phone = f"09{uuid.uuid4().int % 100000000:08d}"
        r1 = self.client.post('/api/auth/register', json={
            'name': 'Người thứ nhất',
            'email': email,
            'phone': phone,
            'password': 'password123'
        })
        self.assertEqual(r1.status_code, 200)

        # Duplicate email
        r2 = self.client.post('/api/auth/register', json={
            'name': 'Người thứ hai',
            'email': email,
            'password': 'password123'
        })
        self.assertEqual(r2.status_code, 409)

        # Duplicate phone
        r3 = self.client.post('/api/auth/register', json={
            'name': 'Người thứ ba',
            'phone': phone,
            'password': 'password123'
        })
        self.assertEqual(r3.status_code, 409)
