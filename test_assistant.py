"""
test_assistant.py — Automated LLM Guardrail Tests (pytest)

Verifies that the Electoral Assistant chatbot correctly enforces
scope boundaries by redirecting out-of-scope queries to the BLO.
"""
import pytest
import sys
import os

# Add project root to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app as flask_app


@pytest.fixture
def client():
    """Create a Flask test client for API testing."""
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test-secret-key'
    with flask_app.test_client() as client:
        yield client


class TestLLMGuardrails:
    """Test suite for LLM scope enforcement and BLO fallback."""

    def test_out_of_scope_baking(self, client):
        """Out-of-scope query ('How do I bake a cake?') must trigger BLO fallback."""
        response = client.post('/api/chat', json={'message': 'How do I bake a cake?'})
        assert response.status_code == 200
        data = response.get_json()
        assert 'reply' in data
        reply = data['reply']
        assert 'Booth Level Officer' in reply or 'BLO' in reply, (
            f"Expected BLO fallback for out-of-scope query, got: {reply}"
        )

    def test_out_of_scope_weather(self, client):
        """Out-of-scope query ('What is the weather?') must trigger BLO fallback."""
        response = client.post('/api/chat', json={'message': 'What is the weather today?'})
        assert response.status_code == 200
        data = response.get_json()
        reply = data['reply']
        assert 'Booth Level Officer' in reply or 'BLO' in reply, (
            f"Expected BLO fallback for weather query, got: {reply}"
        )

    def test_out_of_scope_sports(self, client):
        """Out-of-scope query about sports must trigger BLO fallback."""
        response = client.post('/api/chat', json={'message': 'Who won the cricket match?'})
        assert response.status_code == 200
        data = response.get_json()
        reply = data['reply']
        assert 'Booth Level Officer' in reply or 'BLO' in reply, (
            f"Expected BLO fallback for sports query, got: {reply}"
        )

    def test_in_scope_voting(self, client):
        """In-scope query about voting should NOT trigger BLO fallback."""
        response = client.post('/api/chat', json={'message': 'how to vote'})
        assert response.status_code == 200
        data = response.get_json()
        reply = data['reply']
        assert 'Vote Now' in reply or 'vote' in reply.lower(), (
            f"Expected voting instructions, got: {reply}"
        )

    def test_in_scope_section49a(self, client):
        """In-scope query about Section 49A should return legal information."""
        response = client.post('/api/chat', json={'message': 'What is Section 49A?'})
        assert response.status_code == 200
        data = response.get_json()
        reply = data['reply']
        assert 'Section 49A' in reply or 'tendered' in reply.lower(), (
            f"Expected Section 49A info, got: {reply}"
        )

    def test_greeting_response(self, client):
        """Greeting 'hi' should return the mandated welcome message."""
        response = client.post('/api/chat', json={'message': 'hi'})
        assert response.status_code == 200
        data = response.get_json()
        reply = data['reply']
        assert 'Welcome' in reply, (
            f"Expected greeting response, got: {reply}"
        )

    def test_empty_message_rejected(self, client):
        """Empty message should be rejected with 400."""
        response = client.post('/api/chat', json={'message': ''})
        assert response.status_code == 400

    def test_contact_officer(self, client):
        """Query about contacting an officer should return BLO info."""
        response = client.post('/api/chat', json={'message': 'how to contact election officer'})
        assert response.status_code == 200
        data = response.get_json()
        reply = data['reply']
        assert 'Booth Level Officer' in reply or 'BLO' in reply, (
            f"Expected BLO contact info, got: {reply}"
        )

    def test_view_vote_different_from_cast_vote(self, client):
        """'how to view my vote' and 'how to vote' should produce different responses."""
        res_vote = client.post('/api/chat', json={'message': 'how to vote'})
        res_view = client.post('/api/chat', json={'message': 'how to view my vote'})
        reply_vote = res_vote.get_json()['reply']
        reply_view = res_view.get_json()['reply']
        assert reply_vote != reply_view, (
            f"'how to vote' and 'how to view my vote' returned identical responses"
        )
