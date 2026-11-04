import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from utils.llm import get_llm, get_response_text, invoke_with_fallback


class LlmResponseTests(unittest.TestCase):
    def test_normalizes_legacy_string_content(self):
        response = SimpleNamespace(content="SELECT 1")

        self.assertEqual(get_response_text(response), "SELECT 1")

    def test_extracts_text_from_provider_content_blocks(self):
        response = SimpleNamespace(
            content=[
                {"type": "text", "text": "SELECT 1"},
                {"type": "signature", "signature": "ignored"},
                {"type": "text", "text": "SELECT 2"},
            ]
        )

        self.assertEqual(
            get_response_text(response), "SELECT 1\nSELECT 2"
        )

    def test_falls_back_to_an_alternate_model_after_provider_error(self):
        primary = Mock()
        primary.invoke.side_effect = RuntimeError("503 unavailable")
        fallback = Mock()
        fallback.invoke.return_value = SimpleNamespace(content="OK")

        with patch.dict(
            "os.environ",
            {"GROQ_MODEL": "groq-primary", "GROQ_API_KEY": "test-key"},
        ):
            with patch("utils.llm._active_model", None):
                with patch(
                    "utils.llm.get_llm", side_effect=[primary, fallback]
                ) as factory:
                    response = invoke_with_fallback("prompt")

        self.assertEqual(get_response_text(response), "OK")
        self.assertEqual(factory.call_args_list[0].kwargs["model"], "groq-primary")
        self.assertEqual(
            factory.call_args_list[1].kwargs["model"], "openai/gpt-oss-20b"
        )

    @patch("utils.llm.ChatGroq")
    def test_configures_groq_without_exposing_key(self, chat_groq):
        with patch.dict(
            "os.environ",
            {
                "GROQ_API_KEY": "test-key",
                "GROQ_MODEL": "openai/gpt-oss-20b",
            },
        ):
            get_llm(temperature=0.1)

        options = chat_groq.call_args.kwargs
        self.assertEqual(options["model"], "openai/gpt-oss-20b")
        self.assertEqual(options["api_key"], "test-key")
        self.assertEqual(options["timeout"], 20)
        self.assertEqual(options["max_retries"], 0)

    def test_missing_api_key_fails_before_attempting_provider(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("utils.llm.get_llm") as factory:
                with self.assertRaisesRegex(EnvironmentError, "GROQ_API_KEY"):
                    invoke_with_fallback("prompt")

        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()