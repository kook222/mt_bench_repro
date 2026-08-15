import unittest
from unittest import mock

from mtbench_repro.client import ChatClient, ChatClientError


class ChatClientFailureTest(unittest.TestCase):
    def _client_with_response(self, response):
        client = ChatClient.mock()
        client._mock = False
        client.provider = "openai_compatible"
        client.max_retries = 2
        client.retry_delay = 0.0
        client._chat_openai_compatible = lambda **_: response
        return client

    def test_empty_provider_response_is_not_returned_as_parseable_text(self):
        client = self._client_with_response("")

        with self.assertRaises(ChatClientError):
            client.chat([{"role": "user", "content": "test"}])

    def test_nonempty_response_is_returned(self):
        client = self._client_with_response("[[A]]")

        self.assertEqual(
            client.chat([{"role": "user", "content": "test"}]),
            "[[A]]",
        )

    def test_ambient_openai_key_is_not_forwarded_to_custom_endpoint(self):
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "production-secret"}):
            with self.assertRaisesRegex(ValueError, "explicit API key"):
                ChatClient._resolve_api_key(
                    None,
                    "openai_compatible",
                    "https://untrusted.example/v1",
                )

            self.assertEqual(
                ChatClient._resolve_api_key(
                    "EMPTY",
                    "openai_compatible",
                    "http://localhost:8000/v1",
                ),
                "EMPTY",
            )
            self.assertEqual(
                ChatClient._resolve_api_key(
                    "",
                    "openai_compatible",
                    "https://untrusted.example/v1",
                ),
                "",
            )

    def test_official_endpoint_can_use_matching_environment_key(self):
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "official-key"}):
            self.assertEqual(
                ChatClient._resolve_api_key(
                    None,
                    "openai_compatible",
                    "https://api.openai.com/v1",
                ),
                "official-key",
            )


if __name__ == "__main__":
    unittest.main()
