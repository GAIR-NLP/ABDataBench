"""Regex scanning helpers adapted from seq-extraction/scripts/regex-scan.py."""

import re

from tools.api_client import APIClient


EXCLUDE_CDR3_WORDS = {
    'COPYRIGHT', 'CORRESPONDENCE', 'CONTRIBUTION', 'CONTRIBUTED',
    'CONFLICT', 'CONCEPTUALIZATION', 'COMPREHENSIVE', 'COLLECTED',
    'CHARACTERIZATION', 'CONSTRAINT', 'CONSISTENT', 'CONVALESCENT',
    'CONFIRMATION', 'CONFIDENTIAL', 'COUNTERPART', 'COEFFICIENT',
    'CONSTRUCT', 'CONSTRUCTS', 'CONCENTRATED', 'COMPLEMENT',
    'COMPETITIVE', 'CONVENTIONAL', 'CROSSREACT', 'CROSSREACTIVITY',
}

KNOWN_REAGENT_PREFIXES = {
    'A39', 'A63', 'K03', 'K20', 'PB1', 'SA0',
    'AB1', 'AB2', 'MA1', 'MA5', 'SC-',
}


class RegexScanner:
    """Regex pre-scan engine."""
    ACCESSION_RE = re.compile(r"\b([A-Z]{1,3}(?:[\s_-]+)?\d{5,8}(?:\.\d+)?)\b", re.IGNORECASE)
    NON_ANTIBODY_NAME_PREFIXES = (
        "CDR",
        "IGHV", "IGKV", "IGLV", "IGHD", "IGHJ", "IGKJ", "IGLJ",
        "VH", "VK", "VL", "JH", "JK", "JL",
        "EMD-", "PIIS",
    )

    def scan_all(self, text: str) -> dict:
        genbank_result = self.scan_genbank_ids(text)
        germline_result = self.scan_germline_genes(text)
        cdr3_result = self.scan_cdr3_sequences(text)
        table_result = self.scan_tables(text)
        return {
            "file_size_chars": len(text),
            "pdb_ids": self.scan_pdb_ids(text),
            "genbank": genbank_result,
            "uniprot_ids": self.scan_uniprot_ids(text),
            "germline_genes": germline_result,
            "cdr3_sequences": cdr3_result,
            "dois": self.scan_dois(text),
            "pmids": self.scan_pmids(text),
            "tables": table_result,
            "antibody_name_candidates": self.scan_antibody_names(text),
        }

    def format_hints(self, results: dict) -> str:
        genbank = results["genbank"]
        germline = results["germline_genes"]
        cdr3 = results["cdr3_sequences"]
        table = results["tables"]

        all_germlines = []
        for key in ['IMGT_V_genes', 'IMGT_D_genes', 'IMGT_J_genes',
                     'short_V_genes', 'VDJ_combos', 'VJ_combos']:
            all_germlines.extend(germline.get(key, []))

        lines = ['[Regex Hints]:']
        lines.append(f"- PDB IDs: {', '.join(results['pdb_ids']) or 'None found'}")
        lines.append(f"- GenBank IDs (likely): {', '.join(genbank['likely_genbank']) or 'None found'}")
        lines.append(f"- Nucleotide accessions: {', '.join(genbank['likely_nucleotide']) or 'None found'}")
        lines.append(f"- Protein accessions: {', '.join(genbank['likely_protein']) or 'None found'}")
        if genbank['likely_reagent_catalog']:
            lines.append(f"- Reagent catalog (filtered): {', '.join(genbank['likely_reagent_catalog'])}")
        lines.append(f"- UniProt IDs: {', '.join(results['uniprot_ids']) or 'None found'}")
        lines.append(f"- Germline genes: {', '.join(sorted(set(all_germlines))) or 'None found'}")
        lines.append(f"- CDRH3 candidates: {', '.join(cdr3['CDRH3_candidates']) or 'None found'}")
        lines.append(f"- CDRL3 candidates: {', '.join(cdr3['CDRL3_candidates']) or 'None found'}")
        if cdr3['generic_candidates']:
            lines.append(f"- Other CDR3 candidates: {', '.join(cdr3['generic_candidates'])}")
        lines.append(f"- DOI: {', '.join(results['dois'][:5]) or 'None found'}")
        lines.append(f"- PMID: {', '.join(results['pmids']) or 'None found'}")
        lines.append(f"- Tables: {table['html_table_count']} HTML, {table['markdown_table_count']} Markdown")
        ab_names = results['antibody_name_candidates']
        shown_names = ab_names[:60]
        lines.append(f"- Antibody name candidates: {', '.join(shown_names) or 'None found'}"
                      + (f" (+{len(ab_names)-60} more)" if len(ab_names) > 60 else ""))
        return '\n'.join(lines)

    def suggest_routing(self, results: dict) -> list[str]:
        routes = []
        if results['pdb_ids']:
            routes.append(f"Track A (API Fetch): {len(results['pdb_ids'])} PDB ID(s) → RCSB API")
        if results['genbank']['likely_nucleotide']:
            routes.append(
                f"Track A (API Fetch): {len(results['genbank']['likely_nucleotide'])} nucleotide GenBank ID(s) → NCBI Entrez"
            )
        if results['genbank']['likely_protein']:
            routes.append(
                f"Track A (API Fetch): {len(results['genbank']['likely_protein'])} protein accession(s) → NCBI Entrez"
            )
        if results['genbank']['likely_genbank'] and not (
            results['genbank']['likely_nucleotide'] or results['genbank']['likely_protein']
        ):
            routes.append(f"Track A (API Fetch): {len(results['genbank']['likely_genbank'])} GenBank ID(s) → NCBI Entrez")
        t = results['tables']
        if t['html_table_count'] > 0:
            routes.append(f"Track C (Script Extract): {t['html_table_count']} HTML table(s)")
        if t['markdown_table_count'] > 0:
            routes.append(f"Track C (Script Extract): {t['markdown_table_count']} Markdown table(s)")
        if not results['pdb_ids'] and not results['genbank']['likely_genbank']:
            routes.append('Track A not applicable: No external DB IDs found')
        if t['total_table_count'] == 0:
            routes.append('Track C not applicable: No tables found in document')
        routes.append('Track B (Supplementary): Always check supplementary materials')
        return routes

    # ── Individual Scanners ──

    def scan_pdb_ids(self, text: str) -> list[str]:
        candidates = re.findall(r'\b([0-9][A-Z][A-Z0-9]{2})\b', text)
        skip = {'2WAY', '1WAY'}
        return sorted(set(c for c in candidates if c not in skip))

    def scan_genbank_ids(self, text: str) -> dict:
        results, reagent = [], []
        nucleotide, protein = [], []
        reagent_kw = [
            'catalog', 'cat.', 'cat#', 'cat no', 'thermo', 'fisher',
            'invitrogen', 'sigma', 'abcam', 'bio-rad', 'biolegend',
            'purchased from', 'obtained from', 'dilut', 'μg/ml', 'µg/ml',
        ]
        for match in self.ACCESSION_RE.finditer(text):
            raw = match.group(1)
            c = APIClient.normalize_accession(raw)
            db = APIClient.infer_accession_db(c)
            if db == "unknown":
                continue
            s, e = max(0, match.start() - 120), min(len(text), match.end() + 120)
            ctx = text[s:e].lower()
            is_reagent = (any(kw in ctx for kw in reagent_kw) or
                          any(c.startswith(p) for p in KNOWN_REAGENT_PREFIXES))
            paren = re.search(r'\([^)]*' + re.escape(raw) + r'[^)]*\)', text[s:e], re.IGNORECASE)
            if paren and any(kw in paren.group(0).lower() for kw in ['inc.', 'ltd.', 'corp.']):
                is_reagent = True
            if is_reagent:
                reagent.append(c)
                continue
            results.append(c)
            if db == "nucleotide":
                nucleotide.append(c)
            elif db == "protein":
                protein.append(c)
        return {
            'likely_genbank': sorted(set(results)),
            'likely_nucleotide': sorted(set(nucleotide)),
            'likely_protein': sorted(set(protein)),
            'likely_reagent_catalog': sorted(set(reagent)),
        }

    def scan_uniprot_ids(self, text: str) -> list[str]:
        pat = r'\b([A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9]|[OPQ][0-9][A-Z0-9]{3}[0-9])\b'
        return sorted(set(re.findall(pat, text)))

    def scan_germline_genes(self, text: str) -> dict:
        return {
            'IMGT_V_genes': sorted(set(re.findall(r'(IG[HKL]V\d+-\d+(?:\*\d+)?)', text))),
            'IMGT_D_genes': sorted(set(re.findall(r'(IGHD\d+-\d+(?:\*\d+)?)', text))),
            'IMGT_J_genes': sorted(set(re.findall(r'(IG[HKL]J\d+(?:\*\d+)?)', text))),
            'short_V_genes': sorted(set(re.findall(r'(V[HKL]\d+-\d+(?:\*\d+)?)', text))),
            'short_D_genes': sorted(set(re.findall(r'(D[H]?\d+-\d+(?:\*\d+)?)', text))),
            'short_J_genes': sorted(set(re.findall(r'(J[HKL]\d+(?:\*\d+)?)', text))),
            'VDJ_combos': sorted(set(re.findall(
                r'(V[H]\d+-\d+(?:\*\d+)?/[DJ]H?\d+-?\d*(?:\*\d+)?(?:/[DJ]H?\d+-?\d*(?:\*\d+)?)*)', text))),
            'VJ_combos': sorted(set(re.findall(
                r'(V[KL]\d+-\d+(?:\*\d+)?/J[KL]\d+(?:\*\d+)?)', text))),
            'identity_mentions': len(re.findall(
                r'(?:V[HL]\s*(?:region\s*)?identity\s*\(?%?\)?\s*[:=]?\s*\d+\.?\d*)|'
                r'\d+\.?\d*\s*%\s*(?:identity|identical)', text)),
        }

    def scan_cdr3_sequences(self, text: str) -> dict:
        labeled_h3 = re.findall(r'CDR[-_\s]?H3\s*[:=]?\s*([A-Z]{5,35})', text, re.IGNORECASE)
        labeled_l3 = re.findall(r'CDR[-_\s]?L3\s*[:=]?\s*([A-Z]{5,35})', text, re.IGNORECASE)
        cdrh3_anch = re.findall(r'\b(C[A-Z]{3,28}W)\b', text)
        cdrl3_anch = re.findall(r'\b(C[A-Z]{3,16}[FT])\b', text)
        generic = re.findall(r'\b(C[A-Z]{8,25}[WFTVILG])\b', text)

        def filt(seqs):
            return [s for s in seqs if s.upper() not in EXCLUDE_CDR3_WORDS and len(set(s)) > 3]

        h3 = sorted(set(filt(labeled_h3 + cdrh3_anch)))
        l3 = sorted(set(filt(labeled_l3 + cdrl3_anch)))
        gen = sorted(set(filt(generic)) - set(h3) - set(l3))
        return {'CDRH3_candidates': h3, 'CDRL3_candidates': l3, 'generic_candidates': gen}

    def scan_dois(self, text: str) -> list[str]:
        dois = re.findall(r'(10\.\d{4,}/[^\s,;)\]]+)', text)
        return sorted(set(re.sub(r'[.)]+$', '', d) for d in dois))

    def scan_pmids(self, text: str) -> list[str]:
        return sorted(set(re.findall(r'(?:PMID|PubMed\s*(?:ID)?)\s*[:.]?\s*(\d{6,9})', text, re.IGNORECASE)))

    def scan_tables(self, text: str) -> dict:
        html = re.findall(r'<table[^>]*>.*?</table>', text, re.DOTALL | re.IGNORECASE)
        md = re.findall(r'^(\|[\s:]*-{3,}[\s:]*(?:\|[\s:]*-{3,}[\s:]*)+\|?)$', text, re.MULTILINE)
        return {'html_table_count': len(html), 'markdown_table_count': len(md),
                'total_table_count': len(html) + len(md)}

    def scan_antibody_names(self, text: str) -> list[str]:
        patterns = [
            r'\b(\d{2,5}-[A-Z]\d{1,3})\b',
            r'(?:mAb|MAb|monoclonal antibody)\s+([A-Z0-9][\w-]{2,20})',
            r'\b([a-z]*[mv]i?[rv]?[ui]?mab)\b',
            r'\b([A-Z]{2,6}[-]?\d{3,6})\b',
            r'\b([A-Z]{2,5}\d+(?:\.\d+)?)\b',
            r'\b([A-Z]{1,3}\d{2,5}[a-z]\d{1,3})\b',
            r'(?:[Cc]lone\s+)([A-Z0-9]{2,10})',
            r'(?:antibody\s*\(\s*)([A-Z]{1,3}\d{2,5}[a-z]\d{1,3})(?:\s*\))',
        ]
        fp = {'COVID', 'SARS', 'MERS', 'BA.1', 'BA.2', 'BA.4', 'BA.5',
              'BQ.1', 'XBB', 'WHO', 'FDA', 'EUA', 'ELISA', 'FACS',
              'BSA', 'PBS', 'DMEM', 'RPMI', 'FBS', 'HRP', 'FITC', 'PE'}
        all_c = []
        for p in patterns:
            all_c.extend(re.findall(p, text))
        filtered = []
        for candidate in set(all_c):
            if candidate in fp or len(candidate) < 3:
                continue
            if candidate.upper().startswith(self.NON_ANTIBODY_NAME_PREFIXES):
                continue
            if candidate.lower().endswith("-treated"):
                continue
            if re.fullmatch(r'[A-Z]{2,4}\d{5,}', candidate):
                continue
            filtered.append(candidate)
        return sorted(filtered)
