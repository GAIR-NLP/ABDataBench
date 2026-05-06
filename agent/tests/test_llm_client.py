"""Tests for agent/tools/llm_client.py — mock responses and JSON parsing."""

import json
import unittest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.llm_client import LLMClient
from config import Config


class TestMockSkeletonResponse(unittest.TestCase):
    """Test mock skeleton response includes all 22 eval fields."""

    V3_EVAL_FIELDS = [
        "Antibody_Type", "Antibody_Isotype", "source",
        "Target_Name", "Target_Type", "Cross_Reactivity",
        "Epitope", "Experiment",
        "Binding_Kinetics_KD", "Binding_Kinetics_kon", "Binding_Kinetics_koff", "Binding_EC50",
        "Mechanism_of_Action", "Quantitative_Metric", "Structure",
        "CDRH3_Sequence", "vh_sequence_aa", "vl_sequence_aa",
        "Thermal_Stability_Tm", "In_Vivo_Half_Life", "In_Vivo_Efficacy",
        "Reference_Source",
    ]

    LEGACY_FIELDS = ["Affinity_nM", "PK_source", "External_Database_ID", "Experiment_value"]

    def setUp(self):
        config = Config(mock_llm=True)
        self.client = LLMClient(config)

    def test_mock_response_has_all_v3_fields(self):
        user_msg = "[Paper ID]: test-paper-123\n[Document Text]: some text"
        response = self.client._mock_skeleton_response(user_msg)
        data = json.loads(response)
        ab = data["test-paper-123"]["antibodies"][0]
        for field in self.V3_EVAL_FIELDS:
            self.assertIn(field, ab, f"Mock response missing field: {field}")

    def test_mock_response_no_legacy_fields(self):
        user_msg = "[Paper ID]: test-paper-123\n[Document Text]: some text"
        response = self.client._mock_skeleton_response(user_msg)
        data = json.loads(response)
        ab = data["test-paper-123"]["antibodies"][0]
        for field in self.LEGACY_FIELDS:
            self.assertNotIn(field, ab, f"Mock response has legacy field: {field}")

    def test_mock_response_valid_json(self):
        user_msg = "[Paper ID]: my-paper\n[Document Text]: lorem ipsum"
        response = self.client._mock_skeleton_response(user_msg)
        data = json.loads(response)
        self.assertIn("my-paper", data)
        self.assertIsInstance(data["my-paper"]["antibodies"], list)
        self.assertGreater(len(data["my-paper"]["antibodies"]), 0)


class TestParseJsonResponse(unittest.TestCase):
    """Test JSON parsing from LLM responses."""

    def setUp(self):
        config = Config(mock_llm=True)
        self.client = LLMClient(config)

    def test_parse_clean_json(self):
        result = self.client.parse_json_response('{"key": "value"}')
        self.assertEqual(result, {"key": "value"})

    def test_parse_json_with_markdown_fence(self):
        text = '```json\n{"key": "value"}\n```'
        result = self.client.parse_json_response(text)
        self.assertEqual(result, {"key": "value"})

    def test_parse_json_array(self):
        result = self.client.parse_json_response('[1, 2, 3]')
        self.assertEqual(result, [1, 2, 3])

    def test_parse_json_with_prefix_text(self):
        text = 'Here is the result: {"key": "value"} done.'
        result = self.client.parse_json_response(text)
        self.assertEqual(result, {"key": "value"})

    def test_parse_invalid_json_raises(self):
        with self.assertRaises(ValueError):
            self.client.parse_json_response("not json at all")


class TestRequestFormatting(unittest.TestCase):
    def test_raw_auth_and_thinking_flag_payload(self):
        config = Config(mock_llm=True)
        config.llm_api_key = "raw-key"
        config.llm_use_bearer_auth = False
        config.llm_enable_thinking = False
        client = LLMClient(config)

        headers = client._build_headers()
        payload = client._build_payload(
            model="Qwen3.6-27B",
            system="",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.1,
            max_tokens=16,
            response_format="json",
        )

        self.assertEqual(headers["Authorization"], "raw-key")
        self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(payload["response_format"], {"type": "json_object"})

    def test_bearer_auth_header_when_enabled(self):
        config = Config(mock_llm=True)
        config.llm_api_key = "secret"
        config.llm_use_bearer_auth = True
        client = LLMClient(config)

        self.assertEqual(client._build_headers()["Authorization"], "Bearer secret")


class TestConfigEnvFallbacks(unittest.TestCase):
    def test_empty_optional_env_values_fall_back_to_llm_config(self):
        with patch.dict(
            os.environ,
            {
                "LLM_API_KEY": "shared-key",
                "LLM_API_BASE": "https://llm.example.test",
                "LLM_MODEL": "shared-model",
                "LLM_REVIEW_MODEL": "",
                "VLM_API_KEY": "",
                "VLM_API_BASE": "",
                "SEQUENCE_VLM_API_KEY": "",
                "SEQUENCE_VLM_API_BASE": "",
            },
            clear=False,
        ):
            config = Config(mock_llm=True)

        self.assertEqual(config.llm_review_model, "shared-model")
        self.assertEqual(config.vlm_api_key, "shared-key")
        self.assertEqual(config.vlm_api_base, "https://llm.example.test")
        self.assertEqual(config.sequence_vlm_api_key, "shared-key")
        self.assertEqual(config.sequence_vlm_api_base, "https://llm.example.test")


if __name__ == "__main__":
    unittest.main()
