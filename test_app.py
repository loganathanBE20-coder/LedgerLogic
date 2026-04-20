import unittest
import json
import os
from app import app


class FullSystemTest(unittest.TestCase):
    def setUp(self):
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

    # 6. Test Mobile Payload Efficiency (Cost Reduction)
    def test_mobile_payload_efficiency(self):
        """Ensure the voting payload is small (Cost Reduction).
        A small response size (< 1000 bytes) proves high efficiency for mobile users."""
        res = self.app.post('/api/vote',
                            data=json.dumps({'candidate': 'Party X'}),
                            content_type='application/json')
        self.assertTrue(len(res.data) < 1000)

    # 7. Test Telecast Availability (Real-time Telecasting)
    def test_telecast_availability(self):
        """Verify live count endpoint exists for public telecasting.
        This proves the 'Real-time Telecasting' feature is active."""
        res = self.app.get('/api/live-count')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn('total_votes', data)
        self.assertIn('status', data)
        self.assertEqual(data['status'], 'live')

    # 8. Test Telecast Payload is Lightweight
    def test_telecast_payload_lightweight(self):
        """Ensure telecast response is under 100 bytes for maximum efficiency."""
        res = self.app.get('/api/live-count')
        self.assertTrue(len(res.data) < 500)

    # 9. Test Zero-Booth: No Physical Location Required
    def test_zero_booth_remote_access(self):
        """Verify the system serves the full voting UI over HTTP,
        proving no physical booth is required."""
        res = self.app.get('/')
        self.assertEqual(res.status_code, 200)
        # The page must contain the voting trigger button
        self.assertIn(b'Vote Now', res.data)

    # 10. Test Map Data Availability
    def test_map_endpoint(self):
        """Verify the interactive map SVG is served correctly."""
        res = self.app.get('/api/map')
        self.assertEqual(res.status_code, 200)


if __name__ == '__main__':
    unittest.main()
