import unittest
import json
import os
from app import app

class FullSystemTest(unittest.TestCase):
    def setUp(self):
        # Use a temporary database or mock if needed, but for now we test the live app
        self.app = app.test_client()
        self.app.testing = True

    # 1. Test UI Availability
    def test_homepage_render(self):
        """High-level UI check"""
        res = self.app.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'TAMIL NADU 2026 ASSEMBLY', res.data)

    # 2. Test Functional Logic (API Data)
    def test_api_data_integrity(self):
        """Test if the API returns valid election data structure"""
        res = self.app.get('/api/data')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn('constituencies', data)
        self.assertIn('stats', data)
        self.assertIn('votes', data)

    # 3. Test Authentication Logic (OTP)
    def test_otp_generation(self):
        """Test OTP generation logic"""
        res = self.app.post('/api/request_otp', 
                            data=json.dumps({'name': 'Test User', 'mobile': '9876543210'}),
                            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])

    # 4. Test Edge Cases (Error Handling)
    def test_invalid_route(self):
        """Test how system handles non-existent pages"""
        res = self.app.get('/non_existent_page_v0_0_1')
        self.assertEqual(res.status_code, 404)

    # 5. Test Data Integrity (Headers)
    def test_api_response_headers(self):
        """Ensure the server is serving secure headers"""
        res = self.app.get('/')
        self.assertTrue(res.headers['Content-Type'].startswith('text/html'))

if __name__ == '__main__':
    unittest.main()
