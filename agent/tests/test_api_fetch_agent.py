"""Tests for agent/agents/extract/api_fetch_agent.py."""

import asyncio
import json
import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.extract.api_fetch_agent import APIFetchAgent


class TestAPIFetchAgentBackfill(unittest.TestCase):
    def setUp(self):
        self.agent = APIFetchAgent.__new__(APIFetchAgent)
        self.agent.name = "api_fetch"
        self.agent.logger = logging.getLogger("test.api_fetch")
        self.agent.client = type(
            "FakeClient",
            (),
            {
                "extract_cdrh3_from_variable_region": staticmethod(
                    lambda seq: "CTRDRSECADGSCFGYVMAVW" if seq else ""
                )
            },
        )()

    def test_build_genbank_backfill_records_uses_field_hints(self):
        context = {
            "paper_id": "paper-1",
            "skeleton": {
                "paper-1": {
                    "antibodies": [
                        {
                            "Antibody_Name": "M02-46",
                            "_field_hints": {
                                "vh_sequence_aa": {
                                    "pointer": "GenBank PQ382870; Table-S1-(IGHV4-59/IGKV4-1-clonal-lineage)",
                                    "action": "API Fetch",
                                },
                                "vl_sequence_aa": {
                                    "pointer": "GenBank PQ382870; Table-S1-(IGHV4-59/IGKV4-1-clonal-lineage)",
                                    "action": "API Fetch",
                                },
                            },
                        }
                    ]
                }
            },
        }
        fetched = {
            "PQ382870": {
                "best_variable_regions": {
                    "heavy": {
                        "translation": (
                            "QVQLQESGPGQVKPSETLSLTCTVSGASVTLDYWSWIRQTPERGLEWIGYISYTGRTNYNPSLKSRV"
                            "TISTDTAKNQVSLRLTSVTAADTAVYYCTRDRSECADGSCFGYVMAVWGHGTTVIVSS"
                        )
                    },
                    "light": {
                        "translation": (
                            "DIQMTQSPSTLSASVGDRVTITCRASQSISSWLAWYQQKPGKAPKLLMYKASSLESGVPSRFSGSGSG"
                            "TEFTLTISSLQPDDFATYYCQQYNSYSLTFGPGTKVDLK"
                        )
                    },
                }
            }
        }

        records = self.agent._build_genbank_backfill_records(context, fetched)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["mAb"], "M02-46")
        self.assertTrue(records[0]["VH_sequence"].startswith("QVQLQESGPGQVKPSET"))
        self.assertTrue(records[0]["VL_sequence"].startswith("DIQMTQSPSTLSASVG"))
        self.assertEqual(records[0]["CDRH3"], "CTRDRSECADGSCFGYVMAVW")

    def test_build_genbank_backfill_records_skips_without_matching_hint(self):
        context = {
            "paper_id": "paper-1",
            "skeleton": {
                "paper-1": {
                    "antibodies": [
                        {
                            "Antibody_Name": "M02-46",
                            "_field_hints": {
                                "vh_sequence_aa": {
                                    "pointer": "GenBank AB123456",
                                    "action": "API Fetch",
                                }
                            },
                        }
                    ]
                }
            },
        }
        fetched = {"PQ382870": {"best_variable_regions": {"heavy": {"translation": "QVQLQESG"}}}}

        records = self.agent._build_genbank_backfill_records(context, fetched)

        self.assertEqual(records, [])

    def test_extract_accessions_from_hint_filters_reagent_catalog_context(self):
        hint = {
            "pointer": "GE Healthcare kit BR100050 was used for purification",
            "quote": "catalog no. BR100050",
            "value": "",
        }

        accessions = self.agent._extract_accessions_from_hint(hint)

        self.assertEqual(accessions, [])

    def test_extract_accessions_from_hint_normalizes_common_separator_variants(self):
        hint = {
            "pointer": "GenBank MK_749197 and QHD 43416.1",
            "quote": "",
            "value": "",
        }

        accessions = self.agent._extract_accessions_from_hint(hint)

        self.assertEqual(accessions, ["MK749197", "QHD43416"])

    def test_extract_accessions_from_hint_prefers_exact_over_range_endpoints(self):
        hint = {
            "pointer": "GenBank MK749212",
            "quote": "The accession numbers are GenBank MK_749197 to MK_749219.",
            "value": "",
        }

        candidates = self.agent._extract_accession_candidates_from_hint(hint)

        self.assertEqual(candidates["exact"], ["MK749212"])
        self.assertEqual(candidates["range"], [])

    def test_build_genbank_backfill_records_matches_by_antibody_name_in_accession_description(self):
        context = {
            "paper_id": "paper-1",
            "skeleton": {
                "paper-1": {
                    "antibodies": [
                        {
                            "Antibody_Name": "COVA1-16",
                            "_field_hints": {},
                        }
                    ]
                }
            },
        }
        fetched = {
            "MT599835": {
                "description": "Homo sapiens isolate COVA1-16 anti-SARS-CoV-2 monoclonal antibody heavy chain variable region mRNA",
                "best_variable_regions": {
                    "heavy": {"translation": "QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYYMHWVRQAPGQGLEWMGIINSSGGSTSYAQKFQGRVTMTRDTSTSTVYMELSSLRSEDTAVYYCARPPRNYYDRSGYYQRAEYFQHWGQGTLVTVSS"},
                    "light": None,
                },
                "cds_features": [
                    {"product": "anti-SARS-CoV-2 monoclonal antibody heavy chain variable region"}
                ],
            },
            "MT599919": {
                "description": "Homo sapiens isolate COVA1-16 anti-SARS-CoV-2 monoclonal antibody light chain variable region mRNA",
                "best_variable_regions": {
                    "heavy": None,
                    "light": {"translation": "DIQLTQSPSSLSASVGDRVTITCQASQDISNYLNWYQQRPGKAPKLLIYDASNLETGVPSRFSGSGSGTDFTFTISSLQPEDIATYYCQQYDNPPLTFGGGTKLEIK"},
                },
                "cds_features": [
                    {"product": "anti-SARS-CoV-2 monoclonal antibody light chain variable region"}
                ],
            },
        }

        records = self.agent._build_genbank_backfill_records(context, fetched)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["mAb"], "COVA1-16")
        self.assertTrue(records[0]["VH_sequence"].startswith("QVQLVQSGAEVKKPGA"))
        self.assertTrue(records[0]["VL_sequence"].startswith("DIQLTQSPSSLSASVG"))

    def test_build_genbank_backfill_records_prefers_name_matched_accessions_over_conflicting_hints(self):
        context = {
            "paper_id": "paper-1",
            "skeleton": {
                "paper-1": {
                    "antibodies": [
                        {
                            "Antibody_Name": "PCIN63-71J2a",
                            "_field_hints": {
                                "vh_sequence_aa": {
                                    "pointer": "GenBank MK749212",
                                    "quote": "Heavy chain sequences GenBank MK_749197 to MK_749219",
                                },
                                "vl_sequence_aa": {
                                    "pointer": "GenBank MK749234",
                                    "quote": "Light chain sequences GenBank MK_749220 to MK_749241",
                                },
                            },
                        }
                    ]
                }
            },
        }
        fetched = {
            "MK749212": {
                "description": "Homo sapiens isolate PCIN63-71O-HC anti-HIV immunoglobulin heavy chain variable region mRNA",
                "best_variable_regions": {
                    "heavy": {"translation": "QVQLVQSGAEVKKPGASVRVSCKASGYTFNTCLIHWWRQAPGQGLQWVAWINPLHGAVNYAHQLQGRITVTRDTSIDTAYMELRGLRADDTATYYCTRDSSRDNLEWRLDPWGQGTLVTVSS"},
                },
                "cds_features": [{"product": "anti-HIV immunoglobulin heavy chain variable region"}],
            },
            "MK749207": {
                "description": "Homo sapiens isolate PCIN63-71J2a-HC anti-HIV immunoglobulin heavy chain variable region mRNA",
                "best_variable_regions": {
                    "heavy": {"translation": "QVQLVQSGAEVKKPGASMRVSCKASGYTFTACYIHWFRQAPGQGLEWMGWLNPINGARNNPHKFQGRITLTRDTSTDTAYLELRNLRSDDTAVYYCTRDASRDDRAWRLDPWGQGTLVTVSS"},
                },
                "cds_features": [{"product": "anti-HIV immunoglobulin heavy chain variable region"}],
            },
            "MK749234": {
                "description": "Homo sapiens isolate PCIN63-71L-KC anti-HIV immunoglobulin kappa light chain variable region mRNA",
                "best_variable_regions": {
                    "light": {"translation": "AIRMTQSPATLSASVGDRVTITCRAGQGIGSDLAWYQQKPGQAPKLLIFKASRLKNGVPTRFTGSGFHTEFTLTISGLQSDDFATYYCQVLETFGQGTKVEIK"},
                },
                "cds_features": [{"product": "anti-HIV immunoglobulin kappa light chain variable region"}],
            },
            "MK749232": {
                "description": "Homo sapiens isolate PCIN63-71J2a-KC anti-HIV immunoglobulin kappa light chain variable region mRNA",
                "best_variable_regions": {
                    "light": {"translation": "AIRMTQSPATLSASVGDRVTITCRAGQGIGSDLAWYQQKSGQAPKLLIFKASNLKNGVPPRFSGSGFHTDFTLTISGLQPDDFATYYCQVLETFGQGTKVEIK"},
                },
                "cds_features": [{"product": "anti-HIV immunoglobulin kappa light chain variable region"}],
            },
        }

        records = self.agent._build_genbank_backfill_records(context, fetched)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["mAb"], "PCIN63-71J2a")
        self.assertIn("TRDASRDDRAWRLDP", records[0]["VH_sequence"])
        self.assertTrue(records[0]["VL_sequence"].startswith("AIRMTQSPATLSASVGDRVTITCRAGQGIGSDLAWYQQKSGQ"))
        self.assertEqual(records[0]["_api_source_ids"], "MK749207,MK749232")

    def test_build_genbank_backfill_records_skips_ambiguous_range_only_chain_backfill(self):
        context = {
            "paper_id": "paper-1",
            "skeleton": {
                "paper-1": {
                    "antibodies": [
                        {
                            "Antibody_Name": "PCIN63-77A",
                            "_field_hints": {
                                "vh_sequence_aa": {
                                    "pointer": "GenBank MK_749197 to MK_749219",
                                },
                                "vl_sequence_aa": {
                                    "pointer": "GenBank MK_749220 to MK_749241",
                                },
                            },
                        }
                    ]
                }
            },
        }
        fetched = {
            "MK749214": {
                "description": "Homo sapiens isolate PCIN63-77A-HC anti-HIV immunoglobulin heavy chain variable region mRNA",
                "best_variable_regions": {
                    "heavy": {"translation": "QVQLVQSGAEVKKPGASVRVSCKASGYTFTAYFIHWIRQAPGQGLEWVGWINPLHGAVNYAHKFQGRVSMTRDTSISTAYMELRSLKSDDTAIYYCTTHSSRRDFQWSLDPWGQGTLVTVSS"},
                },
                "cds_features": [{"product": "anti-HIV immunoglobulin heavy chain variable region"}],
            },
            "MK749220": {
                "description": "Homo sapiens isolate PCIN63-UCA-KC anti-HIV immunoglobulin kappa light chain variable region mRNA",
                "best_variable_regions": {
                    "light": {"translation": "DIQMTQSPSTLSASVGDRVTITCRASQSISSWLAWYQQKPGKAPKLLIYKASSLESGVPSRFSGSGSGTEFTLTISSLQPDDFATYYCQQSEAFGQGTKVEIK"},
                },
                "cds_features": [{"product": "anti-HIV immunoglobulin kappa light chain variable region"}],
            },
            "MK749241": {
                "description": "Homo sapiens isolate PCIN63-77F1-KC anti-HIV immunoglobulin kappa light chain variable region mRNA",
                "best_variable_regions": {
                    "light": {"translation": "AIRMTQSPATLSAFVGDRVTITCRASQGIGDDLGWYQQKPGKVPKPLIFKASNLKDGVPSRFSGSGFGTDFTLTINNLQPDDFATYYCQAYESFGQGTKVEIK"},
                },
                "cds_features": [{"product": "anti-HIV immunoglobulin kappa light chain variable region"}],
            },
        }

        records = self.agent._build_genbank_backfill_records(context, fetched)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["mAb"], "PCIN63-77A")
        self.assertIn("TTHSSRRDFQWSLDP", records[0]["VH_sequence"])
        self.assertNotIn("VL_sequence", records[0])
        self.assertEqual(records[0]["_api_source_ids"], "MK749214")

    def test_build_genbank_backfill_records_falls_back_to_cds_features_when_best_regions_missing(self):
        context = {
            "paper_id": "paper-1",
            "skeleton": {
                "paper-1": {
                    "antibodies": [
                        {
                            "Antibody_Name": "2C08",
                            "_field_hints": {
                                "vh_sequence_aa": {
                                    "pointer": "GenBank MW926400",
                                    "action": "API Fetch",
                                },
                                "vl_sequence_aa": {
                                    "pointer": "GenBank MW926423",
                                    "action": "API Fetch",
                                },
                            },
                        }
                    ]
                }
            },
        }
        fetched = {
            "MW926400": {
                "description": "Homo sapiens isolate 368.07.28.GC.2C08.HC immunoglobulin variable region heavy chain mRNA, partial cds",
                "best_variable_regions": {"heavy": None, "light": None},
                "cds_features": [
                    {
                        "product": "immunoglobulin variable region heavy chain",
                        "gene": "",
                        "note": "",
                        "chain": "unknown",
                        "translation": (
                            "EVQLVQSGPEVKKPGTSVKVSCKASGFTFSSSAVQWVRQARGQRLEWIGWIVVGSGNTNYAQKFQERVTITRDMSTNTAYMELSSLRSEDTAVYYCAAAYCSGGSCSDGFDIWGQGTMVTVSS"
                        ),
                    }
                ],
            },
            "MW926423": {
                "description": "Homo sapiens isolate 368.07.28.GC.2C08.LC immunoglobulin variable region light chain mRNA, partial cds",
                "best_variable_regions": {"heavy": None, "light": None},
                "cds_features": [
                    {
                        "product": "immunoglobulin variable region light chain",
                        "gene": "",
                        "note": "",
                        "chain": "unknown",
                        "translation": (
                            "EIVLTQSPGTLSLSPGERATLSCRASQSVSSSYLAWYQQKPGQAPRLLICATSSRATGIPDRFSGSGSGTDFTLTIRRLEPEDFALYYCQQYGSSPWTFGQGTKVEIK"
                        ),
                    }
                ],
            },
        }

        records = self.agent._build_genbank_backfill_records(context, fetched)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["mAb"], "2C08")
        self.assertTrue(records[0]["VH_sequence"].startswith("EVQLVQSGPEVKKPGT"))
        self.assertTrue(records[0]["VL_sequence"].startswith("EIVLTQSPGTLSLSPG"))

    def test_build_pdb_backfill_records_matches_heavy_and_light_chains(self):
        context = {
            "paper_id": "paper-1",
            "skeleton": {
                "paper-1": {
                    "antibodies": [
                        {
                            "Antibody_Name": "SN-101",
                            "Structure": "PDB: 6KX1",
                            "_field_hints": {
                                "Structure": {
                                    "pointer": "PDB 6KX1",
                                    "action": "API Fetch",
                                }
                            },
                        }
                    ]
                }
            },
        }
        fetched = {
            "6KX1": {
                "source": "RCSB PDB",
                "best_chain_sequences": {
                    "heavy": {
                        "sequence": (
                            "MDLRLSCAFIIVLLKGVQSEVNLEESGGGLVQPGGSMKLSCVASGFTFSNYWMNWVRQSPEKGLEWVAQIRLKSDNYATHYAESVKGRF"
                            "TISRDDSKSSVYLQMNNLRAEDTGIYYCTGGVFDYWGQGTTLTVSSSKTTPPSVYPLAPGSAAQTNSMVTLGCLVKGYFPEPVTVTWNSGA"
                        )
                    },
                    "light": {
                        "sequence": (
                            "MKLPVRLLVLMFWIPASSSDVVMTQTPLSLPVSLGDQASISCRSSQSLVHSNGNTYLHWYLQKPGQSPKLLIYKVSNRFSGVPDRFSGSGSGT"
                            "DFTLKISRVEAEDLGVYFCSQSTHVPPWTFGGGTKLEIKRADAAPTVSIFPPSSEQLTSGGA"
                        )
                    },
                },
            }
        }

        records = self.agent._build_pdb_backfill_records(context, fetched)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["mAb"], "SN-101")
        self.assertEqual(records[0]["_api_source_kind"], "pdb")
        self.assertTrue(records[0]["VH_sequence"].endswith("WGQGTTLTVSS"))
        self.assertTrue(records[0]["VL_sequence"].endswith("FGGGTKLEIK"))
        self.assertEqual(records[0]["CDRH3"], "CTRDRSECADGSCFGYVMAVW")

    def test_build_pdb_backfill_records_falls_back_to_nanobody_fasta_entry(self):
        context = {
            "paper_id": "paper-1",
            "skeleton": {
                "paper-1": {
                    "antibodies": [
                        {
                            "Antibody_Name": "Nb55",
                            "Structure": "PDB: 9GXH",
                            "_field_hints": {
                                "Structure": {
                                    "pointer": "PDB 9GXH",
                                    "action": "API Fetch",
                                }
                            },
                        }
                    ]
                }
            },
        }
        fetched = {
            "9GXH": {
                "source": "RCSB PDB",
                "best_chain_sequences": {"heavy": None, "light": None},
                "fasta_entries": [
                    {
                        "header": "9GXH_2|Chains C, D|Thrombin-binding aptamer (TBA)|synthetic construct (32630)",
                        "description": "Thrombin-binding aptamer (TBA)",
                        "chain_role": "other",
                        "sequence": "GGTTGGTGTGGTTGG",
                    },
                    {
                        "header": "9GXH_1|Chains A, B|Nanobody|Lama glama (9844)",
                        "description": "Nanobody",
                        "chain_role": "other",
                        "sequence": "QVQLQESGGGLVQAGGSLRLSCAASGSRFSSNTMTWYRQAPGKQREWVATMRSIGTTRYASSVEGRFTLSRDNAKNTVYLQMNSLKPEDTAVYYCNLRRGGGIYWGQGTQVTVSSHHHHHH",
                    },
                ],
            }
        }

        records = self.agent._build_pdb_backfill_records(context, fetched)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["mAb"], "Nb55")
        self.assertEqual(records[0]["Structure"], "9GXH")
        self.assertEqual(records[0]["_api_source_kind"], "pdb")
        self.assertEqual(
            records[0]["VH_sequence"],
            "QVQLQESGGGLVQAGGSLRLSCAASGSRFSSNTMTWYRQAPGKQREWVATMRSIGTTRYASSVEGRFTLSRDNAKNTVYLQMNSLKPEDTAVYYCNLRRGGGIYWGQGTQVTVSS",
        )

    def test_build_pdb_backfill_records_prioritizes_name_matched_candidate_over_wrong_structure_hint(self):
        context = {
            "paper_id": "paper-1",
            "skeleton": {
                "paper-1": {
                    "antibodies": [
                        {
                            "Antibody_Name": "D19.PA8",
                            "Structure": "PDB: 6XSN",
                            "_field_hints": {"Structure": {"pointer": "PDB 6XSN", "action": "API Fetch"}},
                        }
                    ]
                }
            },
        }
        fetched = {
            "6XSN": {
                "source": "RCSB PDB",
                "pdb_id": "6XSN",
                "fasta_entries": [
                    {"header": "6XSN_1", "description": "VD20.5A4_heavy_chain", "chain_role": "heavy", "sequence": "QVQLQESGPGLVKPSETLSLTCAVSGASISSNYWSWIRQPPGKGLEWIGRIYDPTDSTDYNPSLESRATISKDTSKNHFSLTLSSVTAADTAVYFCARGLWSGYFFWFDVWGPGVLVTVSS"},
                    {"header": "6XSN_2", "description": "VD20.5A4_light_chain", "chain_role": "light", "sequence": "DIQMTQSPSSLSASVGDSVTVTCRASQGIDKELSWYQQKPGKAPTLLIYAASSLQTGVSSRFSGSGSGTDYTLTISSLQPEDVATYYCLQDYATPYSFGQGTKVEIK"},
                ],
                "best_chain_sequences": {},
            },
            "6WAS": {
                "source": "RCSB PDB",
                "pdb_id": "6WAS",
                "fasta_entries": [
                    {"header": "6WAS_1", "description": "GN1_PA8 Fab Heavy chain", "chain_role": "heavy", "sequence": "QVQLVESGGGLAKPGGSLRLSCAASGITFSEDYMHWVRQASGKGLEWVSRISYDSDNTWYADSVKGRFTISRENAKNTLYLQMDSLRAEDTAVYYCARAPVWTGYTSLDVWGRGVLVTVSS"},
                    {"header": "6WAS_2", "description": "GN1_PA8 Fab Light chain", "chain_role": "light", "sequence": "QVVFSQPHSVSGSPGQTVTISCTRSSGSIDNEYVRWYQQRPGSVPTIVIYKDNQRPSGVPDRFSGSIDSSSNSASLAISGLQSEDEADYYCQSSDDNFNWVFGGGTRLTVL"},
                ],
                "best_chain_sequences": {},
            },
        }

        records = self.agent._build_pdb_backfill_records(context, fetched)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["Structure"], "6WAS")
        self.assertTrue(records[0]["VH_sequence"].startswith("QVQLVESGGGLAKPGGSL"))
        self.assertTrue(records[0]["VL_sequence"].startswith("QVVFSQPHSVSGSPGQTV"))

    def test_build_pdb_backfill_records_skips_without_structure_match(self):
        context = {
            "paper_id": "paper-1",
            "skeleton": {
                "paper-1": {
                    "antibodies": [
                        {"Antibody_Name": "SN-101", "Structure": "PDB: 1ABC"}
                    ]
                }
            },
        }
        fetched = {
            "6KX1": {
                "source": "RCSB PDB",
                "best_chain_sequences": {"heavy": {"sequence": "QVQL"}, "light": {"sequence": "DIQM"}},
            }
        }

        records = self.agent._build_pdb_backfill_records(context, fetched)

        self.assertEqual(records, [])

    def test_build_pdb_backfill_records_matches_by_antibody_name_when_structure_missing(self):
        context = {
            "paper_id": "paper-1",
            "skeleton": {
                "paper-1": {
                    "antibodies": [
                        {"Antibody_Name": "AR20.5", "Structure": ""}
                    ]
                }
            },
        }
        fetched = {
            "5T78": {
                "source": "RCSB PDB",
                "pdb_id": "5T78",
                "data": {"struct": {"title": "Crystal structure of therapeutic mAB AR20.5 in complex with MUC1 peptide"}},
                "fasta_entries": [
                    {"header": "5T78_1|Fab fragment AR20.5 - Light Chain", "description": "Fab fragment AR20.5 - Light Chain"},
                    {"header": "5T78_2|Fab Fragment - AR20.5 - Heavy chain", "description": "Fab Fragment - AR20.5 - Heavy chain"},
                ],
                "best_chain_sequences": {
                    "heavy": {
                        "sequence": (
                            "EVKLVESGGGLVAPGGSLKLSCAASGFTFSSYPMSWVRQTPEKRLEWVAYINNGGGNPYYPDTVKGRFTISRDNAKNTLYLQMSSLKSEDTAIYYCIRQYYGFDYWGQGTTLTVSSAKTTPPSV"
                        )
                    },
                    "light": {
                        "sequence": (
                            "DVLMTQTPLSLPVSLGDQASISCRSSQTIVHSNGKIYLEWYLQKPGQSPKLLIYRVSKRFSGVPDRFSGSGSGTDFTLKISRVEAEDLGVYYCFQGSHVPWTFGGGTKLEIKRADAAPTV"
                        )
                    },
                },
            }
        }

        records = self.agent._build_pdb_backfill_records(context, fetched)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["mAb"], "AR20.5")
        self.assertEqual(records[0]["Structure"], "5T78")
        self.assertEqual(records[0]["_api_source_kind"], "pdb")
        self.assertIn("QYYGFDYWGQGTTLTVSS", records[0]["VH_sequence"])

    def test_postprocess_pdb_backfill_records_can_fill_from_llm(self):
        class FakeLLM:
            async def chat(self, **kwargs):
                return type(
                    "Resp",
                    (),
                    {
                        "content": json.dumps(
                            {
                                "mAb": "SM3",
                                "Structure": "5A2K",
                                "VH_sequence": "QVQLQESGGGLVQPGGSMKLSCVASGFTFSNYWMNWVRQSPEKGLEWVAEIRLKSNNYATHYAESVKGRFTISRDDSKSSVYLQMNNLRAEDTGIYYCTGVGQFAYWGQGTTVTV",
                                "VL_sequence": "DIVVTQESALTTSPGETVTLTCRSSTGAVTTSNYANWVQEKPDHLFTGLIGGTNNRAPGVPARFSGSLIGDKAALTITGAQTEDEAIYFCALWYSNHWVFGGGTKLTVL",
                                "CDRH3": "CTGVGQFAYW",
                            },
                            ensure_ascii=False,
                        )
                    },
                )()

            @staticmethod
            def parse_json_response(text):
                return json.loads(text)

        self.agent.llm = FakeLLM()
        self.agent.enable_pdb_llm_postprocess = True
        self.agent.pdb_postprocess_system = "system"
        self.agent.pdb_postprocess_user = "{ANTIBODY_NAME}\n{PDB_SUMMARY_JSON}"
        self.agent.pdb_postprocess_model = "dummy"
        self.agent.pdb_postprocess_max_tokens = 2000
        self.agent.pdb_postprocess_temperature = 0.0
        self.agent.pdb_postprocess_max_fasta_entries = 4

        context = {
            "paper_id": "paper-1",
            "current_phase": "extract",
            "skeleton": {
                "paper-1": {
                    "antibodies": [
                        {
                            "Antibody_Name": "SM3",
                            "Structure": "PDB: 5A2K",
                            "_field_hints": {
                                "Structure": {"pointer": "PDB 5A2K", "action": "API Fetch"},
                            },
                        }
                    ]
                }
            },
        }
        fetched = {
            "5A2K": {
                "source": "RCSB PDB",
                "pdb_id": "5A2K",
                "data": {"struct": {"title": "Crystal structure of scFv-SM3 in complex with APD-TGalNAc-RP"}},
                "fasta_entries": [
                    {
                        "header": "5A2K_1|Chain A|IG LAMBDA-1 CHAIN V REGION S43",
                        "description": "IG LAMBDA-1 CHAIN V REGION S43",
                        "chain_label": "Chain A",
                        "chain_id": "A",
                        "chain_role": "scfv",
                        "sequence": "QVQLQESGGGLVQPGGSMKLSCVASGFTFSNYWMNWVRQSPEKGLEWVAEIRLKSNNYATHYAESVKGRFTISRDDSKSSVYLQMNNLRAEDTGIYYCTGVGQFAYWGQGTTVTVSASSGGGGSGGGGGSSGSSDIVVTQESALTTSPGETVTLTCRSSTGAVTTSNYANWVQEKPDHLFTGLIGGTNNRAPGVPARFSGSLIGDKAALTITGAQTEDEAIYFCALWYSNHWVFGGGTKLTVL",
                    }
                ],
                "best_chain_sequences": {},
            }
        }

        records = asyncio.run(
            self.agent._postprocess_pdb_backfill_records(context, fetched, heuristic_records=[])
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["Structure"], "5A2K")
        self.assertEqual(records[0]["_api_source_kind"], "pdb")
        self.assertEqual(records[0]["CDRH3"], "CTGVGQFAYW")
        self.assertTrue(records[0]["VH_sequence"].startswith("QVQLQESGGGLVQPGGS"))
        self.assertTrue(records[0]["VL_sequence"].startswith("DIVVTQESALTTSPGE"))

    def test_postprocess_pdb_backfill_records_falls_back_to_heuristic_on_llm_failure(self):
        class BrokenLLM:
            async def chat(self, **kwargs):
                raise RuntimeError("boom")

            @staticmethod
            def parse_json_response(text):
                raise RuntimeError("boom")

        self.agent.llm = BrokenLLM()
        self.agent.enable_pdb_llm_postprocess = True
        self.agent.pdb_postprocess_system = "system"
        self.agent.pdb_postprocess_user = "{ANTIBODY_NAME}"
        self.agent.pdb_postprocess_model = "dummy"
        self.agent.pdb_postprocess_max_tokens = 2000
        self.agent.pdb_postprocess_temperature = 0.0
        self.agent.pdb_postprocess_max_fasta_entries = 4

        context = {
            "paper_id": "paper-1",
            "current_phase": "extract",
            "skeleton": {
                "paper-1": {
                    "antibodies": [
                        {
                            "Antibody_Name": "SN-101",
                            "Structure": "PDB: 6KX1",
                            "_field_hints": {"Structure": {"pointer": "PDB 6KX1", "action": "API Fetch"}},
                        }
                    ]
                }
            },
        }
        heuristic_records = [
            {
                "mAb": "SN-101",
                "Structure": "6KX1",
                "VH_sequence": "QVQLQESGPGQVKPSETLSLTC",
                "VL_sequence": "DIQMTQSPSTLSASVGDRVTI",
                "CDRH3": "CTRDRSECADGSCFGYVMAVW",
                "_api_source_ids": "6KX1",
                "_api_source_kind": "pdb",
            }
        ]
        fetched = {
            "6KX1": {
                "source": "RCSB PDB",
                "pdb_id": "6KX1",
                "data": {"struct": {"title": "SN-101 complex"}},
                "fasta_entries": [],
                "best_chain_sequences": {},
            }
        }

        records = asyncio.run(
            self.agent._postprocess_pdb_backfill_records(context, fetched, heuristic_records=heuristic_records)
        )

        self.assertEqual(records, heuristic_records)
