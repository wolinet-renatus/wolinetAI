import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure package root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wolinet import WolinetAI, AsyncWolinetAI
from wolinet.types import ChatMessage, ChatCompletionResponse, EmbeddingResponse, RerankResponse


class TestWolinetClient(unittest.TestCase):
    def setUp(self):
        self.client = WolinetAI(base_url="https://api.wolinet.com", api_key="sk-test-token", timeout=15.0)

    def test_init_parameters(self):
        self.assertEqual(self.client.base_url, "https://api.wolinet.com")
        self.assertEqual(self.client.api_key, "sk-test-token")
        self.assertEqual(self.client.timeout, 15.0)
        self.assertEqual(self.client._headers["Authorization"], "Bearer sk-test-token")
        self.assertEqual(self.client._headers["Content-Type"], "application/json")

    def test_default_base_url_and_env(self):
        with patch.dict("os.environ", {"WOLINET_BASE_URL": "https://custom.wolinet.com", "WOLINET_API_KEY": "sk-env-key"}):
            client = WolinetAI()
            self.assertEqual(client.base_url, "https://custom.wolinet.com")
            self.assertEqual(client.api_key, "sk-env-key")

    @patch("httpx.Client.post")
    def test_chat_completion_sync(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "wolinex-coder",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello from Wolinet AI!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        res = self.client.chat.completions.create(
            model="wolinex-coder",
            messages=[{"role": "user", "content": "Hi"}],
        )

        self.assertIsInstance(res, ChatCompletionResponse)
        self.assertEqual(res.choices[0].message.content, "Hello from Wolinet AI!")
        self.assertEqual(res.model, "wolinex-coder")

    @patch("httpx.Client.post")
    def test_embeddings_sync(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "object": "list",
            "data": [{"index": 0, "object": "embedding", "embedding": [0.1, 0.2, 0.3]}],
            "model": "wolinex-embed",
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        res = self.client.embeddings.create(model="wolinex-embed", input="Hello")
        self.assertIsInstance(res, EmbeddingResponse)
        self.assertEqual(len(res.data[0].embedding), 3)

    @patch("httpx.Client.get")
    def test_status_sync(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "brand": "Wolinet AI",
            "gateway": {"status": "healthy"},
            "inference": {"model_count": 2},
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        status = self.client.status()
        self.assertEqual(status["brand"], "Wolinet AI")
        self.assertEqual(status["gateway"]["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
