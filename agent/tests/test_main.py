import unittest
import httpx

from main import (
    _is_retryable_paper_error,
    _paper_retry_delay_seconds,
    build_benchmark_predictions,
)


class TestBenchmarkPredictionExport(unittest.TestCase):
    def test_filters_chain_level_and_germline_records(self):
        predictions = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {"Antibody_Name": "28D9", "vh_sequence_aa": "AAA"},
                    {"Antibody_Name": "28D9/KJ2", "vl_sequence_aa": "BBB"},
                    {"Antibody_Name": "1C8-H3", "vh_sequence_aa": "CCC"},
                    {"Antibody_Name": "IGKV1-9*01/IGKJ1*01", "vl_sequence_aa": "DDD"},
                    {"Antibody_Name": "H3L1", "vh_sequence_aa": "EEE", "vl_sequence_aa": "FFF"},
                ],
            }
        }

        benchmark_predictions, stats = build_benchmark_predictions(predictions)

        kept_names = [
            ab["Antibody_Name"]
            for ab in benchmark_predictions["paper-1"]["antibodies"]
        ]
        self.assertEqual(kept_names, ["28D9", "H3L1"])
        self.assertEqual(stats["kept"], 2)
        self.assertEqual(stats["dropped"], 3)

    def test_normalizes_generic_mab_type_from_isotype_for_benchmark(self):
        predictions = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "2C08",
                        "Antibody_Type": "mAb",
                        "Antibody_Isotype": "Human IgG",
                    },
                    {
                        "Antibody_Name": "Fab-1",
                        "Antibody_Type": "Fab",
                        "Antibody_Isotype": "Human IgG1",
                    },
                ],
            }
        }

        benchmark_predictions, _ = build_benchmark_predictions(predictions)

        antibodies = benchmark_predictions["paper-1"]["antibodies"]
        self.assertEqual(antibodies[0]["Antibody_Type"], "IgG")
        self.assertEqual(antibodies[1]["Antibody_Type"], "Fab")
        self.assertEqual(predictions["paper-1"]["antibodies"][0]["Antibody_Type"], "mAb")


class TestBatchRetryHelpers(unittest.TestCase):
    def test_retryable_http_status_is_detected(self):
        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(504, request=request)
        exc = httpx.HTTPStatusError("gateway timeout", request=request, response=response)
        self.assertTrue(_is_retryable_paper_error(exc))

    def test_non_retryable_http_status_is_not_detected(self):
        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(400, request=request)
        exc = httpx.HTTPStatusError("bad request", request=request, response=response)
        self.assertFalse(_is_retryable_paper_error(exc))

    def test_retryable_message_fallback_is_detected(self):
        exc = RuntimeError("Server error '504 Gateway Time-out' for url 'https://example.com'")
        self.assertTrue(_is_retryable_paper_error(exc))

    def test_retry_delay_is_bounded(self):
        self.assertEqual(_paper_retry_delay_seconds(0), 5)
        self.assertEqual(_paper_retry_delay_seconds(1), 10)
        self.assertEqual(_paper_retry_delay_seconds(10), 60)


if __name__ == "__main__":
    unittest.main()
