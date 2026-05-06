"""Tests for agent/tools/api_client.py."""

import asyncio
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.api_client import APIClient


class TestAPIClientHelpers(unittest.TestCase):
    def test_normalize_accession_repairs_common_separator_variants(self):
        self.assertEqual(APIClient.normalize_accession("MK_749197"), "MK749197")
        self.assertEqual(APIClient.normalize_accession("mk-749198"), "MK749198")
        self.assertEqual(APIClient.normalize_accession(" QHD 43416.1 "), "QHD43416")

    def test_infer_accession_db(self):
        self.assertEqual(APIClient.infer_accession_db("MT599835"), "nucleotide")
        self.assertEqual(APIClient.infer_accession_db("MK_749197"), "nucleotide")
        self.assertEqual(APIClient.infer_accession_db("PQ382870"), "nucleotide")
        self.assertEqual(APIClient.infer_accession_db("QHD43416"), "protein")
        self.assertEqual(APIClient.infer_accession_db("QHD_43416.1"), "protein")

    def test_fetch_genbank_fasta_exposes_normalized_from_in_result(self):
        client = APIClient(mock_mode=True)

        result = asyncio.run(client.fetch_genbank_fasta("MK_749197"))

        self.assertEqual(result["id"], "MK749197")
        self.assertEqual(result["normalized_from"], "MK_749197")

    def test_extract_variable_domain_from_heavy_chain(self):
        heavy_full = (
            "MDLRLSCAFIIVLLKGVQSEVNLEESGGGLVQPGGSMKLSCVASGFTFSNYWMNWVRQSPEKGLEWVAQIRLKSDNYATHYAESVKGRF"
            "TISRDDSKSSVYLQMNNLRAEDTGIYYCTGGVFDYWGQGTTLTVSSSKTTPPSVYPLAPGSAAQTNSMVTLGCLVKGYFPEPVTVTWNSGA"
        )
        domain = APIClient.extract_variable_domain_from_chain(heavy_full, "heavy")
        self.assertEqual(
            domain,
            "EESGGGLVQPGGSMKLSCVASGFTFSNYWMNWVRQSPEKGLEWVAQIRLKSDNYATHYAESVKGRFTISRDDSKSSVYLQMNNLRAEDTGIYYCTGGVFDYWGQGTTLTVSS",
        )

    def test_extract_variable_domain_from_light_chain(self):
        light_full = (
            "MKLPVRLLVLMFWIPASSSDVVMTQTPLSLPVSLGDQASISCRSSQSLVHSNGNTYLHWYLQKPGQSPKLLIYKVSNRFSGVPDRFSGSGSGT"
            "DFTLKISRVEAEDLGVYFCSQSTHVPPWTFGGGTKLEIKRADAAPTVSIFPPSSEQLTSGGA"
        )
        domain = APIClient.extract_variable_domain_from_chain(light_full, "light")
        self.assertEqual(
            domain,
            "DVVMTQTPLSLPVSLGDQASISCRSSQSLVHSNGNTYLHWYLQKPGQSPKLLIYKVSNRFSGVPDRFSGSGSGTDFTLKISRVEAEDLGVYFCSQSTHVPPWTFGGGTKLEIK",
        )

    def test_parse_pdb_fasta(self):
        fasta_text = (
            ">6KX1_2|Chain B|Fab Fragment-SN-101-Light chain|Mus musculus (10090)\n"
            "DIQMTQSPSTLSASVG\n"
            ">6KX1_1|Chain A|Fab Fragment-SN-101-Heavy chain|Mus musculus (10090)\n"
            "QVQLQESGPGQVKPSE\n"
        )
        entries = APIClient._parse_pdb_fasta(fasta_text, "6KX1")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["chain_role"], "light")
        self.assertEqual(entries[1]["chain_role"], "heavy")

    def test_parse_pdb_fasta_treats_nanobody_as_heavy_chain(self):
        fasta_text = (
            ">9GXH_1|Chains A, B|Nanobody|Lama glama (9844)\n"
            "QVQLQESGGGLVQAGGSLRLSCAASGSRFSSNTMTWYRQAPGKQREWVATMRSIGTTRYASSVEGRF\n"
        )
        entries = APIClient._parse_pdb_fasta(fasta_text, "9GXH")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["chain_role"], "heavy")

    def test_parse_pdb_fasta_recognizes_underscore_heavy_light_descriptions(self):
        fasta_text = (
            ">6XLZ_1|Chain B|NHP_D11A.F2_Fab_Heavy_chain|synthetic construct (32630)\n"
            "QLQLQESGPGLVKPSETLSLTCTVSDGSIRDYWWNWIRQPPGKGLEWIGRIDSVVNTYYNPSLKSRV\n"
            ">6XLZ_2|Chain C|NHP_D11A.F2_Fab_Light_Chain|synthetic construct (32630)\n"
            "EVVFTQPHSVSGSPGQTVTISCTRSSGSLDSEYVQWYQQRPGRAPTIVIYRDNQRPSGVPDRFSGSID\n"
        )
        entries = APIClient._parse_pdb_fasta(fasta_text, "6XLZ")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["chain_role"], "heavy")
        self.assertEqual(entries[1]["chain_role"], "light")

    def test_parse_pdb_fasta_recognizes_hc_kc_short_names(self):
        fasta_text = (
            ">9KYZ_1|Chain C|mAb975HC|synthetic construct (32630)\n"
            "QVQLQESGGGLVQPGGSMKLSCVASGFTFSNYWMNWVRQSPEKGLEWVAEIRLKSDNYATHYAESVKGRFTISRDDSKSSVYLQMNNLRAEDTGIYYCTGVGQFAYWGQGTLVTVSS\n"
            ">9KYZ_2|Chain D|mAb975KC|synthetic construct (32630)\n"
            "DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCALWYSNHWVFGGGTKLTVL\n"
        )
        entries = APIClient._parse_pdb_fasta(fasta_text, "9KYZ")
        self.assertEqual(entries[0]["chain_role"], "heavy")
        self.assertEqual(entries[1]["chain_role"], "light")

    def test_extract_scfv_domains_from_single_chain_sequence(self):
        heavy = (
            "QVQLQESGGGLVQPGGSMKLSCVASGFTFSNYWMNWVRQSPEKGLEWVAEIRLKSDNYATHYAESVKGRFTISRDDSKSSVYLQMNNLRAEDTGIYYCTGVGQFAYWGQGTLVTVSS"
        )
        linker = "SGGGGSGGGGGSSGS"
        light = (
            "DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCALWYSNHWVFGGGTKLTVL"
        )
        scfv = heavy + linker + light
        heavy_domain, light_domain = APIClient.extract_scfv_domains(scfv)
        self.assertEqual(heavy_domain, heavy)
        self.assertEqual(light_domain, light)

    def test_extract_scfv_domains_from_lambda_like_single_chain_sequence(self):
        heavy = (
            "QVQLQESGGGLVQPGGSMKLSCVASGFTFSNYWMNWVRQSPEKGLEWVAEIRLKSNNYATHYAESVKGRFTISRDDSKSSVYLQMNNLRAEDTGIYYCTGVGQFAYWGQGTTVTV"
        )
        linker = "SASSGGGGSGGGGGSSGSS"
        light = (
            "DIVVTQESALTTSPGETVTLTCRSSTGAVTTSNYANWVQEKPDHLFTGLIGGTNNRAPGVPARFSGSLIGDKAALTITGAQTEDEAIYFCALWYSNHWVFGGGTKLTVL"
        )
        scfv = heavy + linker + light
        heavy_domain, light_domain = APIClient.extract_scfv_domains(scfv)
        self.assertEqual(heavy_domain, heavy)
        self.assertEqual(light_domain, light)

    def test_select_pdb_chain_can_use_scfv_entry_for_both_chains(self):
        heavy = (
            "QVQLQESGGGLVQPGGSMKLSCVASGFTFSNYWMNWVRQSPEKGLEWVAEIRLKSDNYATHYAESVKGRFTISRDDSKSSVYLQMNNLRAEDTGIYYCTGVGQFAYWGQGTLVTVSS"
        )
        linker = "SGGGGSGGGGGSSGS"
        light = (
            "DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCALWYSNHWVFGGGTKLTVL"
        )
        entry = APIClient._build_pdb_fasta_entry(
            "5A2K_1|Chain A|IG LAMBDA-1 CHAIN V REGION S43|synthetic construct (32630)",
            heavy + linker + light,
            "5A2K",
        )
        self.assertEqual(entry["chain_role"], "scfv")
        self.assertIsNotNone(APIClient._select_pdb_chain([entry], "heavy"))
        self.assertIsNotNone(APIClient._select_pdb_chain([entry], "light"))

    def test_extract_variable_domain_from_signal_peptide_prefixed_heavy_chain(self):
        heavy_full = (
            "MGWSCIILFLVATATGVHSHLQLQESGPGLVKPSETLSLTCAVSGGSSSDYWWSWIRQPPGKGLEWIGRIDSIGNTYYNPSLRSRVTLSVDTSKNQFSLELTSVTAADTAVYYCARPYCAIGRCYESWGQGVLVTVSS"
        )
        domain = APIClient.extract_variable_domain_from_chain(heavy_full, "heavy")
        self.assertEqual(
            domain,
            "HLQLQESGPGLVKPSETLSLTCAVSGGSSSDYWWSWIRQPPGKGLEWIGRIDSIGNTYYNPSLRSRVTLSVDTSKNQFSLELTSVTAADTAVYYCARPYCAIGRCYESWGQGVLVTVSS",
        )

    def test_extract_variable_domain_from_evvftq_light_chain(self):
        light_full = (
            "MGWSCIILFLVATATGSVTEVVFTQPHSVSGSPGQTVTISCTRTSGSIDSEYVQWYQQRPGSAPTIVIYRDNQRPSGVPDRFSGSIDSSSNSASLAISGLKSEDEADYYCQSSDDSYNWVFGGGTRLTVLGQPKAAPSVTLFPPSSEELQANKATLVCLISDFYPGAVTVAWKADSSPVKAGVETTTPSKQSNNKYAASSYLSLTPEQWKSHRSYSCQVTHEGSTVEKTVAPTECS"
        )
        domain = APIClient.extract_variable_domain_from_chain(light_full, "light")
        self.assertEqual(
            domain,
            "EVVFTQPHSVSGSPGQTVTISCTRTSGSIDSEYVQWYQQRPGSAPTIVIYRDNQRPSGVPDRFSGSIDSSSNSASLAISGLKSEDEADYYCQSSDDSYNWVFGGGTRLTVL",
        )

    def test_extract_chain_infos_from_record(self):
        feature_heavy = type(
            "Feature",
            (),
            {
                "type": "CDS",
                "location": "1..360",
                "qualifiers": {
                    "product": ["immunoglobulin heavy chain variable region"],
                    "protein_id": ["AAA00001.1"],
                    "translation": ["QVQLQESGPGQVKPSETLSLTC"],
                },
            },
        )()
        feature_light = type(
            "Feature",
            (),
            {
                "type": "CDS",
                "location": "361..690",
                "qualifiers": {
                    "product": ["immunoglobulin light chain variable region"],
                    "protein_id": ["AAA00002.1"],
                    "translation": ["DIQMTQSPSTLSASVGDRVTI"],
                },
            },
        )()
        record = type("Record", (), {"features": [feature_heavy, feature_light]})()

        infos = APIClient.extract_chain_infos_from_record(record, "PQ382870")

        self.assertEqual(len(infos), 2)
        self.assertEqual(infos[0]["chain_type"], "VH")
        self.assertEqual(infos[1]["chain_type"], "VL")
        self.assertEqual(infos[0]["protein_id"], "AAA00001.1")
        self.assertEqual(infos[1]["protein_id"], "AAA00002.1")

    def test_extract_chain_infos_from_protein_record(self):
        record = type(
            "Record",
            (),
            {
                "id": "QHD43416.1",
                "description": "surface glycoprotein heavy chain variable region",
                "seq": "QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYYMHWVRQAPGQGLEWMGIINSSGGSTSYAQKFQGRVTMT",
            },
        )()

        infos = APIClient.extract_chain_infos_from_protein_record(record, "QHD43416")

        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0]["chain_type"], "VH")
        self.assertEqual(infos[0]["protein_id"], "QHD43416.1")

    def test_extract_cdrh3_prefers_imgt_numbering_when_available(self):
        vh = (
            "QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYYMHWVRQAPGQGLEWMGIINSSGGSTSYAQKFQGRVTMTRDTSTSTVYMELSSLRSEDTAVYY"
            "CARPPRNYYDRSGYYQRAEYFQHWGQGTLVTVSS"
        )

        class FakeChain:
            def __init__(self, seq, scheme):
                self.cdr3_seq = "CARPPRNYYDRSGYYQRAEYFQHW" if scheme == "imgt" else "WRONG"

        with patch.object(APIClient, "_load_abnumber_chain_class", return_value=FakeChain):
            self.assertEqual(
                APIClient.extract_cdrh3_from_variable_region(vh),
                "CARPPRNYYDRSGYYQRAEYFQHW",
            )

    def test_extract_cdrh3_falls_back_to_chothia_when_imgt_numbering_fails(self):
        vh = (
            "QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYYMHWVRQAPGQGLEWMGIINSSGGSTSYAQKFQGRVTMTRDTSTSTVYMELSSLRSEDTAVYY"
            "CARPPRNYYDRSGYYQRAEYFQHWGQGTLVTVSS"
        )

        class FakeChain:
            def __init__(self, seq, scheme):
                if scheme == "imgt":
                    raise RuntimeError("numbering failed")
                self.cdr3_seq = "CARPPRNYYDRSGYYQRAEYFQHW"

        with patch.object(APIClient, "_load_abnumber_chain_class", return_value=FakeChain):
            self.assertEqual(
                APIClient.extract_cdrh3_from_variable_region(vh),
                "CARPPRNYYDRSGYYQRAEYFQHW",
            )

    def test_extract_cdrh3_expands_numbering_core_to_include_c_and_w(self):
        vh = (
            "QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYYMHWVRQAPGQGLEWMGIINSSGGSTSYAQKFQGRVTMTRDTSTSTVYMELSSLRSEDTAVYY"
            "CARPPRNYYDRSGYYQRAEYFQHWGQGTLVTVSS"
        )

        class FakeChain:
            def __init__(self, seq, scheme):
                self.cdr3_seq = "ARPPRNYYDRSGYYQRAEYFQH"

        with patch.object(APIClient, "_load_abnumber_chain_class", return_value=FakeChain):
            self.assertEqual(
                APIClient.extract_cdrh3_from_variable_region(vh),
                "CARPPRNYYDRSGYYQRAEYFQHW",
            )

    def test_extract_cdrh3_falls_back_to_regex_when_numbering_unavailable(self):
        vh = (
            "QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYYMHWVRQAPGQGLEWMGIINSSGGSTSYAQKFQGRVTMTRDTSTSTVYMELSSLRSEDTAVYY"
            "CARPPRNYYDRSGYYQRAEYFQHWGQGTLVTVSS"
        )

        with patch.object(APIClient, "_load_abnumber_chain_class", return_value=None):
            self.assertEqual(
                APIClient.extract_cdrh3_from_variable_region(vh),
                "CARPPRNYYDRSGYYQRAEYFQHW",
            )
