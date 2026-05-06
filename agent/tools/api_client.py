"""PDB / NCBI API client."""

import asyncio
import logging
import re

import httpx

logger = logging.getLogger(__name__)


class APIClient:
    AA_ALPHABET = set("ACDEFGHIKLMNPQRSTVWY")
    NUCLEOTIDE_ACCESSION_RE = re.compile(r"^[A-Z]{1,2}\d{5,8}$")
    PROTEIN_ACCESSION_RE = re.compile(r"^[A-Z]{3}\d{5}$")

    def __init__(
        self,
        tracer=None,
        mock_mode: bool = False,
        mock_latency_ms: int = 80,
        ncbi_email: str = "",
        ncbi_api_key: str | None = None,
    ):
        self.tracer = tracer
        self.mock_mode = mock_mode
        self.mock_latency_ms = mock_latency_ms
        self.ncbi_email = ncbi_email
        self.ncbi_api_key = ncbi_api_key

    async def fetch_pdb(self, pdb_id: str, trace_fields: dict | None = None) -> dict:
        clean_id = pdb_id.strip().upper()
        url = f"https://data.rcsb.org/rest/v1/core/entry/{clean_id}"
        span_id = self._start_span("api.fetch_pdb", clean_id, trace_fields)
        if self.mock_mode:
            await asyncio.sleep(self.mock_latency_ms / 1000)
            self._end_span(span_id, "success", mocked=True)
            return self._mock_pdb_result(clean_id)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
                fasta_entries = await self._fetch_pdb_fasta(client, clean_id)
                if resp.status_code == 200:
                    self._end_span(
                        span_id,
                        "success",
                        http_status=resp.status_code,
                        chain_count=len(fasta_entries),
                    )
                    return {
                        "source": "RCSB PDB",
                        "pdb_id": clean_id,
                        "data": resp.json(),
                        "fasta_entries": fasta_entries,
                        "best_chain_sequences": {
                            "heavy": self._select_pdb_chain(fasta_entries, "heavy"),
                            "light": self._select_pdb_chain(fasta_entries, "light"),
                        },
                        "confidence": "Level 1",
                    }
                self._end_span(span_id, "error", http_status=resp.status_code)
                return {"source": "RCSB PDB", "pdb_id": clean_id, "error": resp.status_code}
        except Exception as e:
            logger.warning("PDB fetch failed for %s: %s", clean_id, e)
            self._end_span(span_id, "error", error=str(e))
            return {"source": "RCSB PDB", "pdb_id": clean_id, "error": str(e)}

    async def fetch_genbank_fasta(self, genbank_id: str, trace_fields: dict | None = None) -> dict:
        raw_genbank_id = str(genbank_id or "").strip()
        genbank_id = self.normalize_accession(genbank_id)
        normalized_from = raw_genbank_id if raw_genbank_id and raw_genbank_id.upper() != genbank_id else None
        span_trace_fields = dict(trace_fields or {})
        if normalized_from:
            span_trace_fields["normalized_from"] = normalized_from
            logger.info("Normalized GenBank accession %s -> %s", raw_genbank_id, genbank_id)
        span_id = self._start_span("api.fetch_genbank_fasta", genbank_id, span_trace_fields)
        if self.mock_mode:
            await asyncio.sleep(self.mock_latency_ms / 1000)
            self._end_span(span_id, "success", mocked=True)
            result = self._mock_genbank_result(genbank_id)
            if normalized_from:
                result["normalized_from"] = normalized_from
            return result

        try:
            result = await asyncio.to_thread(self._fetch_genbank_record_via_entrez, genbank_id)
            if normalized_from:
                result["normalized_from"] = normalized_from
            self._end_span(
                span_id,
                "success",
                http_status=200,
                fetch_method=result.get("fetch_method"),
                cds_count=len(result.get("cds_features", [])),
                normalized_from=normalized_from,
            )
            return result
        except Exception as entrez_error:
            logger.warning("GenBank Entrez fetch failed for %s: %s", genbank_id, entrez_error)
            try:
                fallback = await self._fetch_genbank_fasta_via_http(genbank_id)
                fallback["warning"] = str(entrez_error)
                if normalized_from:
                    fallback["normalized_from"] = normalized_from
                self._end_span(
                    span_id,
                    "success",
                    http_status=200,
                    fetch_method=fallback.get("fetch_method"),
                    degraded=True,
                    normalized_from=normalized_from,
                )
                return fallback
            except Exception as fallback_error:
                _fallback_err_msg = str(fallback_error)
                logger.warning("GenBank fallback fetch failed for %s: %s", genbank_id, _fallback_err_msg)
                self._end_span(span_id, "error", error=_fallback_err_msg, normalized_from=normalized_from)
            result = {"source": "NCBI GenBank", "id": genbank_id, "error": _fallback_err_msg}
            if normalized_from:
                result["normalized_from"] = normalized_from
            return result

    @classmethod
    def normalize_accession(cls, accession: str) -> str:
        clean = str(accession or "").strip().upper()
        if not clean:
            return ""

        clean = re.sub(r"^[^A-Z0-9]+|[^A-Z0-9.]+$", "", clean)
        compact = re.sub(r"\s+", "", clean)
        candidates = [
            compact,
            re.sub(r"(?<=[A-Z])[_-]+(?=\d)", "", compact),
        ]
        for candidate in candidates:
            core = re.sub(r"\.\d+$", "", candidate)
            if cls.NUCLEOTIDE_ACCESSION_RE.fullmatch(core) or cls.PROTEIN_ACCESSION_RE.fullmatch(core):
                return core
        return compact

    @classmethod
    def infer_accession_db(cls, accession: str) -> str:
        clean = cls.normalize_accession(accession)
        if cls.NUCLEOTIDE_ACCESSION_RE.fullmatch(clean):
            return "nucleotide"
        if cls.PROTEIN_ACCESSION_RE.fullmatch(clean):
            return "protein"
        return "unknown"

    @staticmethod
    def _parse_fasta(fasta_text: str) -> str:
        lines = fasta_text.strip().split("\n")
        return "".join(l.strip() for l in lines if not l.startswith(">"))

    async def _fetch_pdb_fasta(self, client: httpx.AsyncClient, pdb_id: str) -> list[dict]:
        url = f"https://www.rcsb.org/fasta/entry/{pdb_id}/display"
        resp = await client.get(url)
        if resp.status_code != 200:
            return []
        return self._parse_pdb_fasta(resp.text, pdb_id)

    @classmethod
    def _parse_pdb_fasta(cls, fasta_text: str, pdb_id: str) -> list[dict]:
        entries = []
        header = None
        chunks = []
        for raw_line in fasta_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header:
                    entries.append(cls._build_pdb_fasta_entry(header, "".join(chunks), pdb_id))
                header = line[1:]
                chunks = []
            else:
                chunks.append(line)
        if header:
            entries.append(cls._build_pdb_fasta_entry(header, "".join(chunks), pdb_id))
        return [entry for entry in entries if entry.get("sequence")]

    @classmethod
    def _build_pdb_fasta_entry(cls, header: str, sequence: str, pdb_id: str) -> dict:
        parts = header.split("|")
        chain_label = parts[1].strip() if len(parts) > 1 else ""
        description = parts[2].strip() if len(parts) > 2 else header
        organism = parts[3].strip() if len(parts) > 3 else ""
        chain_id_match = re.search(r"Chain\s+([A-Za-z0-9]+)", chain_label)
        normalized_sequence = cls.normalize_protein_sequence(sequence)
        return {
            "pdb_id": pdb_id,
            "header": header,
            "chain_label": chain_label,
            "chain_id": chain_id_match.group(1) if chain_id_match else "",
            "description": description,
            "organism": organism,
            "sequence": normalized_sequence,
            "chain_role": cls._infer_pdb_chain_role(description, normalized_sequence),
        }

    @staticmethod
    def _has_scfv_linker(sequence: str) -> bool:
        seq = APIClient.normalize_protein_sequence(sequence)
        if not seq:
            return False
        return bool(re.search(r"G{2,4}S(?:G{2,4}S){1,4}", seq))

    @classmethod
    def _infer_pdb_chain_role(cls, description: str, sequence: str = "") -> str:
        raw_text = (description or "").lower()
        text = re.sub(r"[_-]+", " ", raw_text)
        if sequence:
            heavy_seq, light_seq = cls.extract_scfv_domains(sequence)
            if heavy_seq and light_seq:
                return "scfv"
        if re.search(r"\bnanobody\b|\bvhh\b|single[- ]domain antibody|camelid antibody fragment", text):
            return "heavy"
        if re.search(r"\bscfv\b|single[- ]chain fv|single[- ]chain variable fragment", text):
            return "scfv"
        if re.search(r"\bheavy\s+chain\b|fab(?:\s+fragment)?[^a-z0-9]*heavy\s+chain|immunoglobulin heavy", text):
            return "heavy"
        if re.search(r"\b(?:hc|vh)\b|(?:hc|vh)$|heavy[_ ]?chain|variable[_ ]?heavy", text):
            return "heavy"
        if re.search(r"\blight\s+chain\b|fab(?:\s+fragment)?[^a-z0-9]*light\s+chain|immunoglobulin (?:kappa |lambda )?light", text):
            return "light"
        if re.search(r"\b(?:kc|lc|vl)\b|(?:kc|lc|vl)$|kappa|lambda|variable[_ ]?light", text):
            return "light"
        return "other"

    @classmethod
    def _select_pdb_chain(cls, entries: list[dict], chain_role: str) -> dict | None:
        candidates = [entry for entry in entries if entry.get("chain_role") == chain_role]
        if not candidates:
            candidates = [
                entry for entry in entries
                if entry.get("chain_role") == "scfv"
                and cls.extract_variable_domain_from_chain(entry.get("sequence", ""), chain_role)
            ]
        if not candidates:
            candidates = [
                entry for entry in entries
                if cls.extract_variable_domain_from_chain(entry.get("sequence", ""), chain_role)
            ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda entry: (
                2 if entry.get("chain_role") == chain_role else 1 if entry.get("chain_role") == "scfv" else 0,
                len(cls.extract_variable_domain_from_chain(entry.get("sequence", ""), chain_role)),
            ),
        )

    async def _fetch_genbank_fasta_via_http(self, genbank_id: str) -> dict:
        genbank_id = self.normalize_accession(genbank_id)
        db = "protein" if self.infer_accession_db(genbank_id) == "protein" else "nucleotide"
        url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db={db}&id={genbank_id}&rettype=fasta&retmode=text"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}")
            fasta = resp.text
            seq = self._parse_fasta(fasta)
            description = fasta.splitlines()[0][1:].strip() if fasta.strip().startswith(">") else ""
            chain = self._infer_chain(description, "", description)
            return {
                "source": "NCBI GenBank",
                "id": genbank_id,
                "fasta": fasta,
                "sequence": seq,
                "best_variable_regions": {
                    "heavy": {
                        "translation": seq,
                        "product": description or f"{db} FASTA fallback",
                        "chain": "heavy" if chain == "unknown" else chain,
                        "is_variable_region": False,
                    } if chain in {"heavy", "unknown"} else None,
                    "light": {
                        "translation": seq,
                        "product": description or f"{db} FASTA fallback",
                        "chain": "light",
                        "is_variable_region": False,
                    } if chain == "light" else None,
                },
                "cds_features": [],
                "confidence": "Level 1",
                "fetch_method": f"httpx-{db}-fasta-fallback",
            }

    def _fetch_genbank_record_via_entrez(self, genbank_id: str) -> dict:
        genbank_id = self.normalize_accession(genbank_id)
        try:
            from Bio import Entrez, SeqIO
        except ImportError as exc:
            raise RuntimeError(
                "Biopython is required for GenBank CDS translation fetch. "
                "Install biopython in the active conda environment."
            ) from exc

        Entrez.email = self.ncbi_email or "unknown@example.com"
        if self.ncbi_api_key:
            Entrez.api_key = self.ncbi_api_key
        db = self.infer_accession_db(genbank_id)

        if db == "protein":
            with Entrez.efetch(db="protein", id=genbank_id, rettype="gp", retmode="text") as handle:
                record = SeqIO.read(handle, "genbank")
            return self._parse_protein_record(record, genbank_id)

        with Entrez.efetch(db="nucleotide", id=genbank_id, rettype="gb", retmode="text") as handle:
            record = SeqIO.read(handle, "genbank")

        return self._parse_genbank_record(record, genbank_id)

    def fetch_genbank_chain_infos(self, accession: str, preferred_chain: str | None = None):
        """Fetch VH/VL CDS translation info from a GenBank nucleotide accession.

        Returns a list by default. When `preferred_chain` is provided, returns the
        first matching chain dict or None.
        """
        raw_accession = str(accession or "").strip()
        accession = self.normalize_accession(accession)
        normalized_from = raw_accession if raw_accession and raw_accession.upper() != accession else None
        if normalized_from:
            logger.info("Normalized GenBank accession %s -> %s", raw_accession, accession)
        try:
            from Bio import Entrez, SeqIO
        except ImportError as exc:
            raise RuntimeError(
                "Biopython is required for GenBank chain inspection. "
                "Install biopython in the active conda environment."
            ) from exc

        Entrez.email = self.ncbi_email or "unknown@example.com"
        if self.ncbi_api_key:
            Entrez.api_key = self.ncbi_api_key
        db = self.infer_accession_db(accession)
        if db == "protein":
            with Entrez.efetch(db="protein", id=accession, rettype="gp", retmode="text") as handle:
                record = SeqIO.read(handle, "genbank")
            chain_infos = self.extract_chain_infos_from_protein_record(record, accession)
        else:
            with Entrez.efetch(db="nucleotide", id=accession, rettype="gb", retmode="text") as handle:
                record = SeqIO.read(handle, "genbank")
            chain_infos = self.extract_chain_infos_from_record(record, accession)
        if normalized_from:
            for info in chain_infos:
                info["normalized_from"] = normalized_from
        if preferred_chain:
            preferred = preferred_chain.strip().upper()
            for info in chain_infos:
                if info["chain_type"] == preferred:
                    return info
            return None
        return chain_infos

    @classmethod
    def _parse_genbank_record(cls, record, genbank_id: str) -> dict:
        cds_features = []
        for feature in getattr(record, "features", []):
            if getattr(feature, "type", "") != "CDS":
                continue

            qualifiers = getattr(feature, "qualifiers", {}) or {}
            translation = cls.normalize_protein_sequence(cls._first_qualifier(qualifiers, "translation"))
            if not translation:
                continue

            product = cls._first_qualifier(qualifiers, "product")
            gene = cls._first_qualifier(qualifiers, "gene")
            note = " ".join(qualifiers.get("note", []))
            chain = cls._infer_chain(product, gene, note)
            is_variable_region = cls._is_variable_region(product, gene, note)
            cds_features.append(
                {
                    "product": product,
                    "gene": gene,
                    "note": note,
                    "protein_id": cls._first_qualifier(qualifiers, "protein_id"),
                    "translation": translation,
                    "location": str(getattr(feature, "location", "")),
                    "chain": chain,
                    "is_variable_region": is_variable_region,
                }
            )

        heavy = cls._select_best_feature(cds_features, "heavy")
        light = cls._select_best_feature(cds_features, "light")
        return {
            "source": "NCBI GenBank",
            "id": genbank_id,
            "record_id": getattr(record, "id", genbank_id),
            "description": getattr(record, "description", ""),
            "organism": getattr(record, "annotations", {}).get("organism", ""),
            "cds_features": cds_features,
            "best_variable_regions": {
                "heavy": heavy,
                "light": light,
            },
            "sequence": (heavy or {}).get("translation", ""),
            "confidence": "Level 1",
            "fetch_method": "biopython-entrez",
        }

    @classmethod
    def _parse_protein_record(cls, record, accession: str) -> dict:
        description = getattr(record, "description", "")
        chain = cls._infer_chain(description, "", description)
        sequence = cls.normalize_protein_sequence(getattr(record, "seq", ""))
        feature = {
            "product": description,
            "gene": "",
            "note": description,
            "protein_id": getattr(record, "id", accession),
            "translation": sequence,
            "location": "",
            "chain": chain,
            "is_variable_region": cls._is_variable_region(description, "", description),
        }
        heavy = feature if chain == "heavy" else None
        light = feature if chain == "light" else None
        if chain == "unknown" and sequence:
            if 95 <= len(sequence) <= 140:
                heavy = feature
            elif 85 <= len(sequence) <= 130:
                light = feature
        return {
            "source": "NCBI GenBank",
            "id": accession,
            "record_id": getattr(record, "id", accession),
            "description": description,
            "organism": getattr(record, "annotations", {}).get("organism", ""),
            "cds_features": [feature] if sequence else [],
            "best_variable_regions": {
                "heavy": heavy,
                "light": light,
            },
            "sequence": sequence,
            "confidence": "Level 1",
            "fetch_method": "biopython-entrez-protein",
        }

    @classmethod
    def extract_chain_infos_from_record(cls, record, accession: str) -> list[dict]:
        chain_infos = []
        for feature in getattr(record, "features", []):
            if getattr(feature, "type", "") != "CDS":
                continue

            qualifiers = getattr(feature, "qualifiers", {}) or {}
            translation = cls.normalize_protein_sequence(cls._first_qualifier(qualifiers, "translation"))
            if not translation:
                continue

            product = cls._first_qualifier(qualifiers, "product")
            gene = cls._first_qualifier(qualifiers, "gene")
            note = " ".join(qualifiers.get("note", []))
            chain_infos.append(
                {
                    "accession": accession,
                    "chain_type": cls._chain_type_label(product, gene, note),
                    "location": str(getattr(feature, "location", "")),
                    "product": product,
                    "protein_id": cls._first_qualifier(qualifiers, "protein_id"),
                    "translation": translation,
                }
            )
        return chain_infos

    @classmethod
    def extract_chain_infos_from_protein_record(cls, record, accession: str) -> list[dict]:
        description = getattr(record, "description", "")
        sequence = cls.normalize_protein_sequence(getattr(record, "seq", ""))
        if not sequence:
            return []
        return [
            {
                "accession": accession,
                "chain_type": cls._chain_type_label(description, "", description),
                "location": "",
                "product": description,
                "protein_id": getattr(record, "id", accession),
                "translation": sequence,
            }
        ]

    @staticmethod
    def _first_qualifier(qualifiers: dict, key: str) -> str:
        value = qualifiers.get(key, [""])
        if isinstance(value, list):
            return str(value[0]).strip() if value else ""
        return str(value).strip()

    @classmethod
    def normalize_protein_sequence(cls, value: str) -> str:
        return re.sub(r"[^A-Za-z]", "", str(value or "")).upper()

    @classmethod
    def _infer_chain(cls, product: str, gene: str, note: str) -> str:
        text = " ".join(part for part in [product, gene, note] if part).lower()
        if re.search(
            r"immunoglobulin (?:variable region )?heavy chain|"
            r"heavy chain (?:variable|variable region)|"
            r"ighv|vh\b",
            text,
        ):
            return "heavy"
        if re.search(
            r"immunoglobulin (?:variable region )?(?:kappa |lambda )?light chain|"
            r"light chain (?:variable|variable region)|"
            r"igk|igl|vk\b|vl\b|kappa|lambda",
            text,
        ):
            return "light"
        return "unknown"

    @classmethod
    def _chain_type_label(cls, product: str, gene: str, note: str) -> str:
        chain = cls._infer_chain(product, gene, note)
        if chain == "heavy":
            return "VH"
        if chain == "light":
            return "VL"
        return "unknown"

    @staticmethod
    def _is_variable_region(product: str, gene: str, note: str) -> bool:
        text = " ".join(part for part in [product, gene, note] if part).lower()
        return bool(re.search(r"variable region|variable domain|v-region|v region", text))

    @classmethod
    def _select_best_feature(cls, features: list[dict], chain: str) -> dict | None:
        candidates = [feature for feature in features if feature.get("chain") == chain]
        if not candidates:
            return None

        def sort_key(feature: dict) -> tuple[int, int, int]:
            length = len(feature.get("translation", ""))
            if chain == "heavy":
                in_range = 95 <= length <= 140
            else:
                in_range = 90 <= length <= 130
            return (
                1 if feature.get("is_variable_region") else 0,
                1 if in_range else 0,
                length,
            )

        return max(candidates, key=sort_key)

    @classmethod
    def extract_cdrh3_from_variable_region(cls, value: str) -> str:
        seq = cls.normalize_protein_sequence(value)
        if not seq:
            return ""

        numbered = cls._extract_cdrh3_from_numbering(seq)
        if numbered:
            return numbered

        return cls._extract_cdrh3_by_regex(seq)

    @staticmethod
    def _load_abnumber_chain_class():
        try:
            from abnumber import Chain
        except Exception:
            return None
        return Chain

    @classmethod
    def _extract_cdrh3_from_numbering(cls, seq: str) -> str:
        chain_cls = cls._load_abnumber_chain_class()
        if not chain_cls:
            return ""

        for scheme in ("imgt", "chothia"):
            try:
                chain = chain_cls(seq, scheme=scheme)
            except Exception:
                continue
            cdrh3 = cls._extract_cdrh3_from_numbered_chain(chain)
            cdrh3 = cls._expand_numbered_cdrh3_boundaries(cdrh3, seq)
            if cls._is_valid_cdrh3_candidate(cdrh3, seq):
                return cdrh3
        return ""

    @classmethod
    def _extract_cdrh3_from_numbered_chain(cls, chain) -> str:
        for attr in ("cdr3_seq", "cdr3", "hcdr3"):
            value = getattr(chain, attr, "")
            if isinstance(value, str):
                seq = cls.normalize_protein_sequence(value)
                if seq:
                    return seq

        regions = getattr(chain, "regions", None)
        if isinstance(regions, dict):
            for key in ("CDR3", "cdr3", "HCDR3", "hcdr3"):
                value = regions.get(key, "")
                if isinstance(value, str):
                    seq = cls.normalize_protein_sequence(value)
                    if seq:
                        return seq

        getter = getattr(chain, "get_region_seq", None)
        if callable(getter):
            for name in ("CDR3", "cdr3", "HCDR3"):
                try:
                    value = getter(name)
                except Exception:
                    continue
                if isinstance(value, str):
                    seq = cls.normalize_protein_sequence(value)
                    if seq:
                        return seq

        return ""

    @classmethod
    def _is_valid_cdrh3_candidate(cls, cdrh3: str, vh_seq: str) -> bool:
        seq = cls.normalize_protein_sequence(cdrh3)
        vh = cls.normalize_protein_sequence(vh_seq)
        if not seq or not vh:
            return False
        if not (5 <= len(seq) <= 40):
            return False
        if set(seq) - cls.AA_ALPHABET:
            return False
        if seq not in vh:
            return False
        if not seq.startswith("C"):
            return False
        if seq[-1] not in {"W", "F"}:
            return False
        return vh.rfind(seq) >= len(vh) // 2

    @classmethod
    def _expand_numbered_cdrh3_boundaries(cls, cdrh3: str, vh_seq: str) -> str:
        core = cls.normalize_protein_sequence(cdrh3)
        vh = cls.normalize_protein_sequence(vh_seq)
        if not core or not vh:
            return ""
        idx = vh.find(core)
        if idx < 0:
            return core

        start = idx
        end = idx + len(core)
        if start > 0 and vh[start - 1] == "C":
            start -= 1
        if end < len(vh) and vh[end] in {"W", "F"}:
            end += 1
        return vh[start:end]

    @classmethod
    def _extract_cdrh3_by_regex(cls, seq: str) -> str:
        seq = cls.normalize_protein_sequence(seq)
        if not seq:
            return ""

        patterns = [
            r"(C[A-Z]{3,30}?)(WG[A-Z]{1,4})",
            r"(C[A-Z]{3,30}?)(FG[A-Z]{1,4})",
        ]
        for pattern in patterns:
            matches = list(re.finditer(pattern, seq))
            for match in reversed(matches):
                if match.start() < len(seq) // 2:
                    continue
                cdr = match.group(1) + match.group(2)[0]
                if 5 <= len(cdr) <= 30 and set(cdr) <= cls.AA_ALPHABET:
                    return cdr
        return ""

    @classmethod
    def extract_variable_domain_from_chain(cls, value: str, chain: str) -> str:
        seq = cls.normalize_protein_sequence(value)
        if not seq:
            return ""

        if len(seq) >= 180:
            scfv_heavy, scfv_light = cls.extract_scfv_domains(seq)
            if chain == "heavy" and scfv_heavy:
                return scfv_heavy
            if chain == "light" and scfv_light:
                return scfv_light

        return cls._extract_variable_domain_from_chain_no_scfv(seq, chain)

    @classmethod
    def _extract_variable_domain_from_chain_no_scfv(cls, value: str, chain: str) -> str:
        seq = cls.normalize_protein_sequence(value)
        if not seq:
            return ""

        if chain == "heavy":
            start_patterns = [
                r"EESGGG",
                r"EVQL",
                r"QVQL",
                r"DVQL",
                r"QLQL",
                r"HLQL",
                r"LQLQ",
                r"VQPGG",
            ]
            end_patterns = [
                r"C[A-Z]{3,30}?WG[A-Z]{1,8}T[LVI]V?SS",
                r"C[A-Z]{3,30}?FG[A-Z]{1,8}T[LVI]V?SS",
                r"C[A-Z]{3,30}?WG[A-Z]{1,10}TVTV",
                r"C[A-Z]{3,30}?FG[A-Z]{1,10}TVTV",
            ]
            fallback_window = 150
        else:
            start_patterns = [
                r"DIQMTQ",
                r"DIVVTQ",
                r"DVVMTQ",
                r"DIVMTQ",
                r"QSVLTQ",
                r"EIVLTQ",
                r"EVVFTQ",
                r"QVVFSQ",
                r"VVFTQ",
                r"MTQTPS",
                r"VMTQTP",
            ]
            end_patterns = [
                r"C[A-Z]{3,25}?FGGGTR[LVI]TVL",
                r"C[A-Z]{3,25}?FGGGTK[LVI]E?IK",
                r"C[A-Z]{3,25}?FGQGTKV?EIK",
                r"C[A-Z]{3,25}?FG[A-Z]{2,12}LTVL",
                r"C[A-Z]{3,25}?FG[A-Z]{2,12}KLEIK",
                r"C[A-Z]{3,25}?FG[A-Z]{2,12}VK",
            ]
            fallback_window = 130

        start_idx = None
        for pattern in start_patterns:
            match = re.search(pattern, seq[:80])
            if match and (start_idx is None or match.start() < start_idx):
                start_idx = match.start()

        if start_idx is not None:
            tail = seq[start_idx:]
            for pattern in end_patterns:
                match = re.search(pattern, tail)
                if match:
                    return tail[:match.end()]
            return tail[:fallback_window]

        for pattern in end_patterns:
            matches = list(re.finditer(pattern, seq))
            if matches:
                best = max(matches, key=lambda match: match.end())
                window = seq[max(0, best.end() - fallback_window):best.end()]
                return window
        return seq

    @classmethod
    def extract_scfv_domains(cls, value: str) -> tuple[str, str]:
        seq = cls.normalize_protein_sequence(value)
        if not seq or len(seq) < 180:
            return ("", "")

        heavy_starts = cls._find_chain_start_positions(seq, "heavy")
        light_starts = cls._find_chain_start_positions(seq, "light")
        if not heavy_starts or not light_starts:
            return ("", "")

        for heavy_start in heavy_starts:
            next_light = next((idx for idx in light_starts if idx >= heavy_start + 70), None)
            if next_light is None:
                continue
            heavy_segment = seq[heavy_start:next_light]
            light_segment = seq[next_light:]
            heavy_seq = cls._extract_variable_domain_from_chain_no_scfv(heavy_segment, "heavy")
            light_seq = cls._extract_variable_domain_from_chain_no_scfv(light_segment, "light")
            if cls._looks_like_variable_domain(heavy_seq, "heavy") and cls._looks_like_variable_domain(light_seq, "light"):
                return (heavy_seq, light_seq)

        for light_start in light_starts:
            next_heavy = next((idx for idx in heavy_starts if idx >= light_start + 60), None)
            if next_heavy is None:
                continue
            light_segment = seq[light_start:next_heavy]
            heavy_segment = seq[next_heavy:]
            light_seq = cls._extract_variable_domain_from_chain_no_scfv(light_segment, "light")
            heavy_seq = cls._extract_variable_domain_from_chain_no_scfv(heavy_segment, "heavy")
            if cls._looks_like_variable_domain(heavy_seq, "heavy") and cls._looks_like_variable_domain(light_seq, "light"):
                return (heavy_seq, light_seq)

        if cls._has_scfv_linker(seq):
            heavy_seq = cls._extract_variable_domain_from_chain_no_scfv(seq, "heavy")
            light_seq = cls._extract_variable_domain_from_chain_no_scfv(seq, "light")
            if cls._looks_like_variable_domain(heavy_seq, "heavy") and cls._looks_like_variable_domain(light_seq, "light"):
                return (heavy_seq, light_seq)

        return ("", "")

    @classmethod
    def _find_chain_start_positions(cls, seq: str, chain: str) -> list[int]:
        if chain == "heavy":
            start_patterns = [
                r"EESGGG",
                r"EVQL",
                r"QVQL",
                r"DVQL",
                r"QLQL",
                r"HLQL",
                r"LQLQ",
                r"VQPGG",
            ]
            search_limit = min(len(seq), 140)
        else:
            start_patterns = [
                r"DIQMTQ",
                r"DIVVTQ",
                r"DVVMTQ",
                r"DIVMTQ",
                r"QSVLTQ",
                r"EIVLTQ",
                r"EVVFTQ",
                r"QVVFSQ",
                r"VVFTQ",
                r"MTQTPS",
                r"VMTQTP",
            ]
            search_limit = len(seq)

        positions = []
        for pattern in start_patterns:
            for match in re.finditer(pattern, seq[:search_limit]):
                positions.append(match.start())
        return sorted(set(positions))

    @staticmethod
    def _looks_like_variable_domain(seq: str, chain: str) -> bool:
        if not seq:
            return False
        length = len(seq)
        if chain == "heavy":
            return 95 <= length <= 160
        return 85 <= length <= 140

    @classmethod
    def _mock_genbank_result(cls, genbank_id: str) -> dict:
        heavy = (
            "QVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISSGGGSTYYADSVKGRF"
            "TISRDNAKNTLYLQMNSLRAEDTAVYYCARDRSTGYYYYFDYWGQGTLVTVSS"
        )
        light = (
            "DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGT"
            "DFTLTISSLQPEDFATYYCQQYNSYPLTFGQGTKVEIK"
        )
        return {
            "source": "NCBI GenBank",
            "id": genbank_id,
            "record_id": genbank_id,
            "description": "mocked GenBank entry",
            "cds_features": [
                {
                    "product": "immunoglobulin heavy chain variable region",
                    "gene": "IGHV",
                    "note": "",
                    "protein_id": f"{genbank_id}.H",
                    "translation": heavy,
                    "location": "1..360",
                    "chain": "heavy",
                    "is_variable_region": True,
                },
                {
                    "product": "immunoglobulin kappa light chain variable region",
                    "gene": "IGKV",
                    "note": "",
                    "protein_id": f"{genbank_id}.L",
                    "translation": light,
                    "location": "361..690",
                    "chain": "light",
                    "is_variable_region": True,
                },
            ],
            "best_variable_regions": {
                "heavy": {
                    "product": "immunoglobulin heavy chain variable region",
                    "gene": "IGHV",
                    "note": "",
                    "protein_id": f"{genbank_id}.H",
                    "translation": heavy,
                    "location": "1..360",
                    "chain": "heavy",
                    "is_variable_region": True,
                },
                "light": {
                    "product": "immunoglobulin kappa light chain variable region",
                    "gene": "IGKV",
                    "note": "",
                    "protein_id": f"{genbank_id}.L",
                    "translation": light,
                    "location": "361..690",
                    "chain": "light",
                    "is_variable_region": True,
                },
            },
            "sequence": heavy,
            "confidence": "Level 1",
            "fetch_method": "mock",
        }

    @classmethod
    def _mock_pdb_result(cls, pdb_id: str) -> dict:
        heavy_full = (
            "MDLRLSCAFIIVLLKGVQSEVNLEESGGGLVQPGGSMKLSCVASGFTFSNYWMNWVRQSPEKGLEWVAQIRLKSDNYATHYAESVKGRF"
            "TISRDDSKSSVYLQMNNLRAEDTGIYYCTGGVFDYWGQGTTLTVSSSKTTPPSVYPLAPGSAAQTNSMVTLGCLVKGYFPEPVTVTWNSGA"
            "LSSGVHTFPAVLQSDLYTLSSSVTVPSSTWPSQTVTCNVAHPASSTKVDKKIVPRD"
        )
        light_full = (
            "MKLPVRLLVLMFWIPASSSDVVMTQTPLSLPVSLGDQASISCRSSQSLVHSNGNTYLHWYLQKPGQSPKLLIYKVSNRFSGVPDRFSGSGSGT"
            "DFTLKISRVEAEDLGVYFCSQSTHVPPWTFGGGTKLEIKRADAAPTVSIFPPSSEQLTSGGASVVCFLNNFYPKDINVKWKIDGSERQNGV"
            "LNSWTDQDSKDSTYSMSSTLTLTKDEYERHNSYTCEATHKTSTSPIVKSFNRNEC"
        )
        fasta_entries = [
            cls._build_pdb_fasta_entry(
                f"{pdb_id}_1|Chain A|Fab Fragment-SN-101-Heavy chain|Mus musculus (10090)",
                heavy_full,
                pdb_id,
            ),
            cls._build_pdb_fasta_entry(
                f"{pdb_id}_2|Chain B|Fab Fragment-SN-101-Light chain|Mus musculus (10090)",
                light_full,
                pdb_id,
            ),
        ]
        return {
            "source": "RCSB PDB",
            "pdb_id": pdb_id,
            "data": {"mocked": True, "pdb_id": pdb_id},
            "fasta_entries": fasta_entries,
            "best_chain_sequences": {
                "heavy": cls._select_pdb_chain(fasta_entries, "heavy"),
                "light": cls._select_pdb_chain(fasta_entries, "light"),
            },
            "confidence": "Level 1",
        }

    def _start_span(self, name: str, target: str, trace_fields: dict | None):
        if not self.tracer:
            return None
        fields = trace_fields or {}
        return self.tracer.start_span(
            "tool",
            name,
            tool=name,
            target=target,
            **fields,
        )

    def _end_span(self, span_id, status: str, **fields):
        if self.tracer:
            self.tracer.end_span(span_id, status=status, **fields)
