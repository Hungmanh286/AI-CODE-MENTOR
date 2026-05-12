import pytest
import requests
from typing import Optional


class TestAskAPI:
    """Test suite for POST /api/v1/ask endpoint"""

    BASE_URL = "http://app.humata.ai"
    ENDPOINT = "/api/v1/ask"

    def __init__(self):
        self.base_url = self.BASE_URL
        self.endpoint = self.ENDPOINT
        self.bearer_token = None  # Set this with your actual token

    def get_headers(self, token: Optional[str] = None) -> dict:
        """Get request headers with authorization"""
        auth_token = token or self.bearer_token or "YOUR_SECRET_TOKEN"
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "Accept": "*/*",
        }

    def test_ask_basic_question(self):
        """Test basic question asking functionality"""
        payload = {
            "conversationId": "7290fd6b-fe15-4fd3-865e-8010bd8e8a38",
            "model": "gpt-4-turbo-preview",
            "question": "Who is George Washington?",
        }

        response = requests.post(
            f"{self.base_url}{self.endpoint}", headers=self.get_headers(), json=payload
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.json() is not None, "Response body should not be empty"

    def test_ask_with_different_models(self):
        """Test asking questions with different models"""
        models = ["gpt-4-turbo-preview", "gpt-3.5-turbo", "gpt-4"]

        for model in models:
            payload = {
                "conversationId": "7290fd6b-fe15-4fd3-865e-8010bd8e8a38",
                "model": model,
                "question": "What is AI?",
            }

            response = requests.post(
                f"{self.base_url}{self.endpoint}",
                headers=self.get_headers(),
                json=payload,
            )

            assert response.status_code in [200, 400], (
                f"Model {model}: Expected 200 or 400, got {response.status_code}"
            )

    def test_ask_missing_conversation_id(self):
        """Test request without conversationId"""
        payload = {
            "model": "gpt-4-turbo-preview",
            "question": "Who is George Washington?",
        }

        response = requests.post(
            f"{self.base_url}{self.endpoint}", headers=self.get_headers(), json=payload
        )

        assert response.status_code in [400, 422], (
            f"Expected 400 or 422 for missing conversationId, got {response.status_code}"
        )

    def test_ask_missing_question(self):
        """Test request without question"""
        payload = {
            "conversationId": "7290fd6b-fe15-4fd3-865e-8010bd8e8a38",
            "model": "gpt-4-turbo-preview",
        }

        response = requests.post(
            f"{self.base_url}{self.endpoint}", headers=self.get_headers(), json=payload
        )

        assert response.status_code in [400, 422], (
            f"Expected 400 or 422 for missing question, got {response.status_code}"
        )

    def test_ask_empty_question(self):
        """Test request with empty question"""
        payload = {
            "conversationId": "7290fd6b-fe15-4fd3-865e-8010bd8e8a38",
            "model": "gpt-4-turbo-preview",
            "question": "",
        }

        response = requests.post(
            f"{self.base_url}{self.endpoint}", headers=self.get_headers(), json=payload
        )

        assert response.status_code in [400, 422], (
            f"Expected 400 or 422 for empty question, got {response.status_code}"
        )

    def test_ask_unauthorized(self):
        """Test request without authorization token"""
        payload = {
            "conversationId": "7290fd6b-fe15-4fd3-865e-8010bd8e8a38",
            "model": "gpt-4-turbo-preview",
            "question": "Who is George Washington?",
        }

        headers = {"Content-Type": "application/json", "Accept": "*/*"}

        response = requests.post(
            f"{self.base_url}{self.endpoint}", headers=headers, json=payload
        )

        assert response.status_code == 401, (
            f"Expected 401 for unauthorized request, got {response.status_code}"
        )

    def test_ask_invalid_token(self):
        """Test request with invalid authorization token"""
        payload = {
            "conversationId": "7290fd6b-fe15-4fd3-865e-8010bd8e8a38",
            "model": "gpt-4-turbo-preview",
            "question": "Who is George Washington?",
        }

        response = requests.post(
            f"{self.base_url}{self.endpoint}",
            headers=self.get_headers(token="INVALID_TOKEN_12345"),
            json=payload,
        )

        assert response.status_code in [401, 403], (
            f"Expected 401 or 403 for invalid token, got {response.status_code}"
        )

    def test_ask_long_question(self):
        """Test request with very long question"""
        payload = {
            "conversationId": "7290fd6b-fe15-4fd3-865e-8010bd8e8a38",
            "model": "gpt-4-turbo-preview",
            "question": "What is AI? " * 500,  # Very long question
        }

        response = requests.post(
            f"{self.base_url}{self.endpoint}", headers=self.get_headers(), json=payload
        )

        assert response.status_code in [200, 400, 413], (
            f"Expected 200, 400, or 413 for long question, got {response.status_code}"
        )

    def test_ask_special_characters(self):
        """Test request with special characters in question"""
        payload = {
            "conversationId": "7290fd6b-fe15-4fd3-865e-8010bd8e8a38",
            "model": "gpt-4-turbo-preview",
            "question": "Who is @#$%^&*() George Washington? 你好世界",
        }

        response = requests.post(
            f"{self.base_url}{self.endpoint}", headers=self.get_headers(), json=payload
        )

        assert response.status_code == 200, (
            f"Expected 200 for special characters, got {response.status_code}"
        )

    def test_ask_response_structure(self):
        """Test that response has expected structure"""
        payload = {
            "conversationId": "7290fd6b-fe15-4fd3-865e-8010bd8e8a38",
            "model": "gpt-4-turbo-preview",
            "question": "Who is George Washington?",
        }

        response = requests.post(
            f"{self.base_url}{self.endpoint}", headers=self.get_headers(), json=payload
        )

        if response.status_code == 200:
            data = response.json()
            # Add assertions based on expected response structure
            assert isinstance(data, dict), "Response should be a dictionary"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
