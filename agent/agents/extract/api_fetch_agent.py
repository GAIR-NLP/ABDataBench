"""Phase 3 Track A: external database API lookup agent."""

import json
import os
import re
import time
from agents.base_agent import BaseAgent, AgentResult, AgentStatus
from tools.api_client import APIClient
from tools.llm_client import LLMClient
from tools.skill_loader import load_skill_prompt_set


class APIFetchAgent(BaseAgent):
    GENBANK_ACCESSION_RE = re.compile(r"\b([A-Z]{1,3}(?:[\s_-]+)?\d{5,8}(?:\.\d+)?)\b", re.IGNORECASE)
    PDB_ID_RE = re.compile(r"\b([0-9][A-Z0-9]{3})\b")
    ACCESSION_SUPPORT_TERMS = (
        "genbank",
        "accession",
        "ncbi",
        "entrez",
        "sequence",
        "cdrh3",
        "variable region",
        "heavy chain",
        "light chain",
        "vh",
        "vl",
        "cds",
        "translation",
        "mrna",
        "immunoglobulin",
        "antibody",
        "fab",
        "scfv",
        "nanobody",
    )
    ACCESSION_REJECT_TERMS = (
        "catalog",
        "cat.",
        "cat#",
        "cat no",
        "kit",
        "ge healthcare",
        "thermo",
        "invitrogen",
        "sigma",
        "abcam",
        "bio-rad",
        "biolegend",
        "reagent",
    )
    ANTIBODY_FETCH_TERMS = (
        "antibody",
        "immunoglobulin",
        "variable region",
        "heavy chain",
        "light chain",
        "fab",
        "scfv",
        "nanobody",
        "vhh",
    )

    def __init__(self, config):
        super().__init__("api_fetch", config)
        self.client = APIClient(
            tracer=getattr(config, "trace_recorder", None),
            mock_mode=getattr(config, "mock_llm", False),
            ncbi_email=getattr(config, "ncbi_email", ""),
            ncbi_api_key=getattr(config, "ncbi_api_key", None),
        )
        self.llm = LLMClient(config)
        self.enable_pdb_llm_postprocess = bool(
            getattr(config, "enable_pdb_llm_postprocess", True)
        ) and not bool(getattr(config, "mock_llm", False))
        self.pdb_postprocess_model = getattr(config, "pdb_llm_postprocess_model", "") or config.llm_model
        self.pdb_postprocess_max_tokens = int(getattr(config, "pdb_llm_postprocess_max_tokens", 3000))
        self.pdb_postprocess_temperature = float(
            getattr(config, "pdb_llm_postprocess_temperature", 0.0)
        )
        self.pdb_postprocess_max_fasta_entries = int(
            getattr(config, "pdb_llm_postprocess_max_fasta_entries", 8)
        )
        prompts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "prompts")
        prompts = load_skill_prompt_set(
            "pdb-postprocess",
            {
                "system_prompt": os.path.join(prompts_dir, "pdb_postprocess_system.txt"),
                "user_template": os.path.join(prompts_dir, "pdb_postprocess_user.txt"),
            },
        )
        self.pdb_postprocess_system = prompts["system_prompt"]
        self.pdb_postprocess_user = prompts["user_template"]

    async def execute(self, context: dict) -> AgentResult:
        start = time.time()
        agent_span = self._start_span(context, "agent", self.name)
        hints = context.get("regex_hints", {})
        pdb_ids = hints.get("pdb_ids", [])
        genbank_requests = []
        normalized_pairs = []
        for raw_gid in hints.get("genbank", {}).get("likely_genbank", []):
            gid = APIClient.normalize_accession(raw_gid)
            if APIClient.infer_accession_db(gid) == "unknown" or any(item["normalized"] == gid for item in genbank_requests):
                continue
            genbank_requests.append({"raw": raw_gid, "normalized": gid})
            if raw_gid != gid:
                normalized_pairs.append(f"{raw_gid}->{gid}")

        fetched = {}

        try:
            trace_fields = {"paper_id": context.get("paper_id"), "phase": context.get("current_phase"), "agent": self.name}
            for pid in pdb_ids:
                result = await self.client.fetch_pdb(pid, trace_fields=trace_fields)
                if "error" not in result:
                    fetched[pid] = result

            for request in genbank_requests:
                result = await self.client.fetch_genbank_fasta(request["raw"], trace_fields=trace_fields)
                if "error" not in result:
                    fetched[result.get("id", request["normalized"])] = result

            api_records = self._build_genbank_backfill_records(context, fetched)
            pdb_records = self._build_pdb_backfill_records(context, fetched)
            if self.enable_pdb_llm_postprocess:
                pdb_records = await self._postprocess_pdb_backfill_records(
                    context,
                    fetched,
                    pdb_records,
                )
            api_records.extend(pdb_records)
            normalization_summary = f", normalized={normalized_pairs}" if normalized_pairs else ""
            self.logger.info(
                f"API Fetch: {len(fetched)}/{len(pdb_ids)+len(genbank_requests)} successful{normalization_summary}"
            )
            elapsed = round(time.time() - start, 2)
            self._end_span(
                context,
                agent_span,
                status="success",
                elapsed_seconds=elapsed,
                requested=len(pdb_ids) + len(genbank_requests),
                fetched=len(fetched),
                records=len(api_records),
            )
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data={"api_fetched": fetched, "table_records": api_records},
                metrics={"elapsed_seconds": elapsed},
            )
        except Exception as exc:
            self._end_span(context, agent_span, status="error", error=str(exc))
            raise

    @classmethod
    def _extract_accessions_from_hint(cls, hint: dict | None) -> list[str]:
        candidates = cls._extract_accession_candidates_from_hint(hint)
        return candidates["exact"] or candidates["range"]

    @classmethod
    def _extract_accession_candidates_from_hint(cls, hint: dict | None) -> dict[str, list[str]]:
        if not isinstance(hint, dict):
            return {"exact": [], "range": []}
        exact_accessions = []
        range_accessions = []
        for key in ("pointer", "quote", "value"):
            text = str(hint.get(key, ""))
            extracted = []
            for match in cls.GENBANK_ACCESSION_RE.finditer(text):
                acc = APIClient.normalize_accession(match.group(1))
                if APIClient.infer_accession_db(acc) == "unknown":
                    continue
                if cls._hint_accession_looks_plausible(acc, text) and acc not in extracted:
                    extracted.append(acc)
            if not extracted:
                continue
            target = range_accessions if cls._text_suggests_accession_range(text, extracted) else exact_accessions
            for acc in extracted:
                if acc not in target:
                    target.append(acc)
        if exact_accessions:
            return {"exact": exact_accessions, "range": []}
        return {"exact": [], "range": range_accessions}

    @staticmethod
    def _text_suggests_accession_range(text: str, extracted: list[str]) -> bool:
        if len(extracted) < 2:
            return False
        lowered = (text or "").lower()
        return bool(re.search(r"\bto\b|\bthrough\b|\bthru\b|\.\.\.|…|[-–—]", lowered))

    @classmethod
    def _hint_accession_looks_plausible(cls, accession: str, hint_text: str) -> bool:
        lowered = (hint_text or "").lower()
        if not lowered:
            return True
        for match in cls.GENBANK_ACCESSION_RE.finditer(hint_text):
            if APIClient.normalize_accession(match.group(1)) != accession:
                continue
            start = max(0, match.start() - 80)
            end = min(len(hint_text), match.end() + 80)
            window = hint_text[start:end].lower()
            if any(term in window for term in cls.ACCESSION_REJECT_TERMS):
                return False
            if any(term in window for term in cls.ACCESSION_SUPPORT_TERMS):
                return True
        compact = re.sub(r"\s+", "", hint_text)
        return compact.upper() == accession.upper()

    @staticmethod
    def _select_translation(fetch_result: dict, chain: str) -> str:
        best = (fetch_result.get("best_variable_regions") or {}).get(chain)
        if isinstance(best, dict):
            translation = best.get("translation", "")
            if translation:
                return translation
        for feature in fetch_result.get("cds_features", []):
            if not isinstance(feature, dict):
                continue
            translation = str(feature.get("translation", "")).strip()
            if not translation:
                continue
            feature_chain = str(feature.get("chain", "")).strip().lower()
            if feature_chain not in {"heavy", "light"}:
                feature_chain = APIClient._infer_chain(
                    str(feature.get("product", "")),
                    str(feature.get("gene", "")),
                    str(feature.get("note", "")),
                )
            if feature_chain == chain:
                return translation
        return ""

    @classmethod
    def _fetch_result_supports_chain(cls, fetch_result: dict | None, chain: str) -> bool:
        return bool(cls._select_translation(fetch_result or {}, chain))

    def _build_genbank_backfill_records(self, context: dict, fetched: dict) -> list[dict]:
        paper_id = context.get("paper_id", "")
        antibodies = context.get("skeleton", {}).get(paper_id, {}).get("antibodies", [])
        if not antibodies or not fetched:
            return []

        all_ids = [acc for acc, result in fetched.items() if self._fetch_result_supports_antibody_backfill(result)]
        singleton_fallback = len(all_ids) == 1 and len(antibodies) == 1
        records = []

        for ab in antibodies:
            name = str(ab.get("Antibody_Name", "")).strip()
            if not name:
                continue

            field_hints = ab.get("_field_hints", {})
            field_candidates = {
                field: self._extract_accession_candidates_from_hint(field_hints.get(field))
                for field in ("vh_sequence_aa", "vl_sequence_aa", "CDRH3_Sequence")
            }
            field_hint_presence = {
                field: self._hint_has_accession_request(field_hints.get(field))
                for field in ("vh_sequence_aa", "vl_sequence_aa", "CDRH3_Sequence")
            }

            record = {"mAb": name}
            selected_ids = []
            vh_candidates = self._candidate_genbank_ids_for_chain(
                name,
                "heavy",
                field_candidates["vh_sequence_aa"],
                field_hint_presence["vh_sequence_aa"],
                fetched,
                singleton_fallback=singleton_fallback,
                all_ids=all_ids,
            )
            vl_candidates = self._candidate_genbank_ids_for_chain(
                name,
                "light",
                field_candidates["vl_sequence_aa"],
                field_hint_presence["vl_sequence_aa"],
                fetched,
                singleton_fallback=singleton_fallback,
                all_ids=all_ids,
            )
            cdrh3_candidates = []
            if field_hint_presence["CDRH3_Sequence"]:
                cdrh3_candidates = self._candidate_genbank_ids_for_chain(
                    name,
                    "heavy",
                    field_candidates["CDRH3_Sequence"],
                    field_hint_presence["CDRH3_Sequence"],
                    fetched,
                    singleton_fallback=singleton_fallback,
                    all_ids=all_ids,
                )
            if (
                not vh_candidates
                and field_candidates["vh_sequence_aa"] != field_candidates["CDRH3_Sequence"]
                and (
                    field_candidates["CDRH3_Sequence"].get("exact")
                    or field_candidates["CDRH3_Sequence"].get("range")
                )
            ):
                cdrh3_only_candidates = self._candidate_genbank_ids_for_chain(
                    name,
                    "heavy",
                    field_candidates["CDRH3_Sequence"],
                    field_hint_presence["CDRH3_Sequence"],
                    fetched,
                    singleton_fallback=singleton_fallback,
                    all_ids=all_ids,
                )
                for acc in cdrh3_only_candidates:
                    if acc not in vh_candidates:
                        vh_candidates.append(acc)
            if not vh_candidates and not vl_candidates and not cdrh3_candidates:
                continue

            vh_seq = ""
            for acc in vh_candidates:
                fetch_result = fetched.get(acc)
                if not fetch_result:
                    continue
                vh_seq = self._select_translation(fetch_result, "heavy")
                if vh_seq:
                    record["VH_sequence"] = vh_seq
                    selected_ids.append(acc)
                    break

            for acc in vl_candidates:
                fetch_result = fetched.get(acc)
                if not fetch_result:
                    continue
                vl_seq = self._select_translation(fetch_result, "light")
                if vl_seq:
                    record["VL_sequence"] = vl_seq
                    if acc not in selected_ids:
                        selected_ids.append(acc)
                    break

            if not vh_seq:
                for acc in cdrh3_candidates:
                    fetch_result = fetched.get(acc)
                    if not fetch_result:
                        continue
                    vh_seq = self._select_translation(fetch_result, "heavy")
                    if vh_seq:
                        if acc not in selected_ids:
                            selected_ids.append(acc)
                        break
            cdrh3 = self.client.extract_cdrh3_from_variable_region(vh_seq)
            if cdrh3:
                record["CDRH3"] = cdrh3

            if len(record) > 1:
                record["_api_source_ids"] = ",".join(selected_ids)
                record["_api_source_kind"] = "genbank"
                records.append(record)

        return records

    @staticmethod
    def _normalize_name_token(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (value or "").lower())

    @classmethod
    def _antibody_name_aliases(cls, antibody_name: str) -> list[str]:
        raw = (antibody_name or "").strip()
        if not raw:
            return []
        aliases = []
        for candidate in [raw, cls._normalize_name_token(raw)]:
            norm = cls._normalize_name_token(candidate)
            if norm and norm not in aliases:
                aliases.append(norm)
        parts = [cls._normalize_name_token(part) for part in re.split(r"[\s._-]+", raw) if cls._normalize_name_token(part)]
        if parts:
            candidate = parts[-1]
            if len(candidate) >= 3 and candidate not in aliases:
                aliases.append(candidate)
        return aliases

    @classmethod
    def _name_match_score(cls, text: str, antibody_name: str) -> int:
        if not text or not antibody_name:
            return 0
        raw_text = str(text)
        norm_text = cls._normalize_name_token(raw_text)
        full_name = (antibody_name or "").strip()
        score = 0
        if full_name and re.search(rf"\b{re.escape(full_name)}\b", raw_text, re.IGNORECASE):
            score = 4
        full_norm = cls._normalize_name_token(full_name)
        if full_norm and full_norm in norm_text:
            score = max(score, 3)
        for alias in cls._antibody_name_aliases(antibody_name):
            if alias and alias in norm_text:
                score = max(score, 2 if alias != full_norm else 3)
        return score

    @classmethod
    def _text_contains_antibody_name(cls, text: str, antibody_name: str) -> bool:
        return cls._name_match_score(text, antibody_name) > 0

    def _match_genbank_ids_by_antibody_name(self, antibody_name: str, fetched: dict, chain: str | None = None) -> list[str]:
        matches = []
        for acc, fetch_result in fetched.items():
            if not self._fetch_result_supports_antibody_backfill(fetch_result):
                continue
            if chain and not self._fetch_result_supports_chain(fetch_result, chain):
                continue
            haystacks = [
                str(fetch_result.get("description", "")),
                str(fetch_result.get("record_id", "")),
            ]
            for feature in fetch_result.get("cds_features", []):
                haystacks.append(str(feature.get("product", "")))
                haystacks.append(str(feature.get("note", "")))
            score = max((self._name_match_score(text, antibody_name) for text in haystacks), default=0)
            if score > 0:
                matches.append((acc, score))
        matches.sort(key=lambda item: (item[1], self._chain_score(fetched.get(item[0], {}), antibody_name, chain or "heavy")), reverse=True)
        return [acc for acc, _score in matches]

    def _candidate_genbank_ids_for_chain(
        self,
        antibody_name: str,
        chain: str,
        hint_candidates: dict[str, list[str]],
        hint_present: bool,
        fetched: dict,
        singleton_fallback: bool,
        all_ids: list[str],
    ) -> list[str]:
        exact_ids = [
            acc
            for acc in hint_candidates.get("exact", [])
            if acc in fetched and self._fetch_result_supports_chain(fetched.get(acc), chain)
        ]
        range_ids = [
            acc
            for acc in hint_candidates.get("range", [])
            if acc in fetched and self._fetch_result_supports_chain(fetched.get(acc), chain)
        ]
        name_ids = self._match_genbank_ids_by_antibody_name(antibody_name, fetched, chain=chain)
        if name_ids:
            return self._prioritize_chain_matches(name_ids, fetched, antibody_name, chain)
        if exact_ids:
            return self._prioritize_chain_matches(exact_ids, fetched, antibody_name, chain)
        if singleton_fallback and not hint_present and not exact_ids and not range_ids:
            singleton_ids = [
                acc for acc in all_ids if self._fetch_result_supports_chain(fetched.get(acc), chain)
            ]
            return self._prioritize_chain_matches(singleton_ids, fetched, antibody_name, chain)
        if len(range_ids) == 1:
            return self._prioritize_chain_matches(range_ids, fetched, antibody_name, chain)
        return []

    @staticmethod
    def _hint_has_accession_request(hint: dict | None) -> bool:
        if not isinstance(hint, dict):
            return False
        return any(str(hint.get(key, "")).strip() for key in ("pointer", "quote", "value"))

    @classmethod
    def _fetch_result_supports_antibody_backfill(cls, fetch_result: dict | None) -> bool:
        if not isinstance(fetch_result, dict):
            return False
        best_regions = fetch_result.get("best_variable_regions") or {}
        for chain_name in ("heavy", "light"):
            region = best_regions.get(chain_name)
            if isinstance(region, dict) and region.get("translation"):
                return True

        haystacks = [
            str(fetch_result.get("description", "")),
            str(fetch_result.get("record_id", "")),
        ]
        for feature in fetch_result.get("cds_features", []):
            haystacks.extend(
                str(feature.get(key, "")) for key in ("product", "note", "gene")
            )
        text = " ".join(haystacks).lower()
        return any(term in text for term in cls.ANTIBODY_FETCH_TERMS)

    def _match_pdb_ids_by_antibody_name(self, antibody_name: str, fetched: dict) -> list[str]:
        matches = []
        for pdb_id, fetch_result in fetched.items():
            haystacks = [
                str(((fetch_result.get("data") or {}).get("struct") or {}).get("title", "")),
                str(((fetch_result.get("data") or {}).get("struct_keywords") or {}).get("text", "")),
                str(fetch_result.get("pdb_id", "")),
            ]
            for entry in fetch_result.get("fasta_entries", []):
                haystacks.append(str(entry.get("header", "")))
                haystacks.append(str(entry.get("description", "")))
            for chain_name in ("heavy", "light"):
                chain = (fetch_result.get("best_chain_sequences") or {}).get(chain_name) or {}
                haystacks.append(str(chain.get("header", "")))
                haystacks.append(str(chain.get("description", "")))
            if max((self._name_match_score(text, antibody_name) for text in haystacks), default=0) > 0:
                matches.append(pdb_id)
        return matches

    @staticmethod
    def _looks_like_nanobody_entry(entry: dict) -> bool:
        text = " ".join(
            str(entry.get(key, ""))
            for key in ("header", "description", "chain_label", "organism")
        ).lower()
        return bool(re.search(r"\bnanobody\b|\bvhh\b|single[- ]domain antibody|camelid antibody fragment", text))

    @classmethod
    def _select_pdb_chain_entry(cls, pdb_result: dict, chain_name: str) -> dict | None:
        best = (pdb_result.get("best_chain_sequences") or {}).get(chain_name) or {}
        if str(best.get("sequence", "")).strip():
            return best

        fasta_entries = [entry for entry in pdb_result.get("fasta_entries", []) if str(entry.get("sequence", "")).strip()]
        for entry in fasta_entries:
            if str(entry.get("chain_role", "")).strip().lower() == chain_name:
                return entry

        if chain_name == "heavy":
            nanobody_entries = [entry for entry in fasta_entries if cls._looks_like_nanobody_entry(entry)]
            if nanobody_entries:
                return max(nanobody_entries, key=lambda entry: len(str(entry.get("sequence", ""))))

        return None

    def _chain_score(self, fetch_result: dict, antibody_name: str, chain: str) -> tuple[int, int]:
        features = fetch_result.get("cds_features", [])
        haystacks = [str(fetch_result.get("description", ""))]
        for feature in features:
            haystacks.append(" ".join(str(feature.get(key, "")) for key in ("product", "note", "gene")))
        name_score = max((self._name_match_score(text, antibody_name) for text in haystacks), default=0)
        region = (fetch_result.get("best_variable_regions") or {}).get(chain)
        chain_score = 1 if isinstance(region, dict) and region.get("translation") else 0
        return (name_score, chain_score)

    def _prioritize_chain_matches(self, accession_ids: list[str], fetched: dict, antibody_name: str, chain: str) -> list[str]:
        unique_ids = []
        for acc in accession_ids:
            if acc not in unique_ids:
                unique_ids.append(acc)
        return sorted(
            unique_ids,
            key=lambda acc: self._chain_score(fetched.get(acc, {}), antibody_name, chain),
            reverse=True,
        )

    @classmethod
    def _extract_pdb_ids_from_structure(cls, value) -> list[str]:
        text = str(value or "")
        pdb_ids = []
        for match in cls.PDB_ID_RE.finditer(text.upper()):
            code = match.group(1)
            if code not in pdb_ids:
                pdb_ids.append(code)
        return pdb_ids

    def _pdb_candidate_score(self, pdb_result: dict, antibody_name: str) -> tuple[int, int, int]:
        haystacks = [
            str(((pdb_result.get("data") or {}).get("struct") or {}).get("title", "")),
            str(((pdb_result.get("data") or {}).get("struct_keywords") or {}).get("text", "")),
            str(pdb_result.get("pdb_id", "")),
        ]
        for entry in pdb_result.get("fasta_entries", []):
            haystacks.append(str(entry.get("header", "")))
            haystacks.append(str(entry.get("description", "")))
        name_score = max((self._name_match_score(text, antibody_name) for text in haystacks), default=0)
        heavy_entry = self._select_pdb_chain_entry(pdb_result, "heavy")
        light_entry = self._select_pdb_chain_entry(pdb_result, "light")
        heavy_seq = APIClient.extract_variable_domain_from_chain((heavy_entry or {}).get("sequence", ""), "heavy")
        light_seq = APIClient.extract_variable_domain_from_chain((light_entry or {}).get("sequence", ""), "light")
        chain_score = int(bool(heavy_seq)) + int(bool(light_seq))
        total_len = len(heavy_seq) + len(light_seq)
        return (name_score, chain_score, total_len)


    def _build_pdb_backfill_records(self, context: dict, fetched: dict) -> list[dict]:
        paper_id = context.get("paper_id", "")
        antibodies = context.get("skeleton", {}).get(paper_id, {}).get("antibodies", [])
        pdb_results = {key: value for key, value in fetched.items() if value.get("source") == "RCSB PDB"}
        if not antibodies or not pdb_results:
            return []

        all_ids = list(pdb_results.keys())
        singleton_fallback = len(all_ids) == 1 and len(antibodies) == 1
        require_name_evidence = len(antibodies) > 1
        records = []

        for ab in antibodies:
            name = str(ab.get("Antibody_Name", "")).strip()
            if not name:
                continue

            field_hints = ab.get("_field_hints", {})
            structure_ids = set(self._extract_pdb_ids_from_structure(ab.get("Structure")))
            candidate_ids = list(structure_ids)
            candidate_ids.extend(self._extract_pdb_ids_from_structure((field_hints.get("Structure") or {}).get("pointer")))
            candidate_ids.extend(self._extract_pdb_ids_from_structure((field_hints.get("Structure") or {}).get("quote")))
            for code in self._match_pdb_ids_by_antibody_name(name, pdb_results):
                if code not in candidate_ids:
                    candidate_ids.append(code)
            candidate_ids = [code for idx, code in enumerate(candidate_ids) if code not in candidate_ids[:idx]]
            if not candidate_ids and singleton_fallback:
                candidate_ids = all_ids[:]
            if not candidate_ids:
                continue
            candidate_ids = sorted(
                candidate_ids,
                key=lambda code: self._pdb_candidate_score(pdb_results.get(code, {}), name),
                reverse=True,
            )

            record = {"mAb": name}
            for code in candidate_ids:
                pdb_result = pdb_results.get(code)
                if not pdb_result:
                    continue
                candidate_score = self._pdb_candidate_score(pdb_result, name)
                if require_name_evidence and candidate_score[0] == 0 and code not in structure_ids:
                    continue
                record["Structure"] = code
                heavy_entry = self._select_pdb_chain_entry(pdb_result, "heavy")
                light_entry = self._select_pdb_chain_entry(pdb_result, "light")
                heavy_seq = APIClient.extract_variable_domain_from_chain((heavy_entry or {}).get("sequence", ""), "heavy")
                light_seq = APIClient.extract_variable_domain_from_chain((light_entry or {}).get("sequence", ""), "light")
                if heavy_seq:
                    record["VH_sequence"] = heavy_seq
                    cdrh3 = self.client.extract_cdrh3_from_variable_region(heavy_seq)
                    if cdrh3:
                        record["CDRH3"] = cdrh3
                if light_seq:
                    record["VL_sequence"] = light_seq
                if len(record) > 1:
                    break

            if len(record) > 1:
                record["_api_source_ids"] = ",".join(candidate_ids)
                record["_api_source_kind"] = "pdb"
                records.append(record)

        return records

    async def _postprocess_pdb_backfill_records(
        self,
        context: dict,
        fetched: dict,
        heuristic_records: list[dict],
    ) -> list[dict]:
        paper_id = context.get("paper_id", "")
        antibodies = context.get("skeleton", {}).get(paper_id, {}).get("antibodies", [])
        pdb_results = {key: value for key, value in fetched.items() if value.get("source") == "RCSB PDB"}
        if not antibodies or not pdb_results:
            return heuristic_records

        heuristic_by_name = {
            str(record.get("mAb", "")).strip(): record
            for record in heuristic_records
            if str(record.get("mAb", "")).strip()
        }
        all_ids = list(pdb_results.keys())
        singleton_fallback = len(all_ids) == 1 and len(antibodies) == 1
        require_name_evidence = len(antibodies) > 1
        final_records = []

        for ab in antibodies:
            name = str(ab.get("Antibody_Name", "")).strip()
            if not name:
                continue
            candidate_ids = self._candidate_pdb_ids_for_antibody(
                ab,
                name,
                pdb_results,
                all_ids,
                singleton_fallback,
            )
            structure_ids = set(self._extract_pdb_ids_from_structure(ab.get("Structure")))
            heuristic_record = heuristic_by_name.get(name)
            if not candidate_ids:
                if heuristic_record:
                    final_records.append(heuristic_record)
                continue
            llm_record = await self._postprocess_single_pdb_record(
                context,
                ab,
                name,
                candidate_ids,
                pdb_results,
                heuristic_record or {"mAb": name},
                require_name_evidence=require_name_evidence,
                structure_ids=structure_ids,
            )
            merged = self._merge_pdb_backfill_records(
                name,
                candidate_ids,
                heuristic_record,
                llm_record,
            )
            if len(merged) > 1:
                final_records.append(merged)

        return final_records

    def _candidate_pdb_ids_for_antibody(
        self,
        ab: dict,
        antibody_name: str,
        pdb_results: dict,
        all_ids: list[str],
        singleton_fallback: bool,
    ) -> list[str]:
        field_hints = ab.get("_field_hints", {})
        candidate_ids = self._extract_pdb_ids_from_structure(ab.get("Structure"))
        candidate_ids.extend(self._extract_pdb_ids_from_structure((field_hints.get("Structure") or {}).get("pointer")))
        candidate_ids.extend(self._extract_pdb_ids_from_structure((field_hints.get("Structure") or {}).get("quote")))
        for code in self._match_pdb_ids_by_antibody_name(antibody_name, pdb_results):
            if code not in candidate_ids:
                candidate_ids.append(code)
        candidate_ids = [code for idx, code in enumerate(candidate_ids) if code not in candidate_ids[:idx]]
        if not candidate_ids and singleton_fallback:
            candidate_ids = all_ids[:]
        return candidate_ids

    async def _postprocess_single_pdb_record(
        self,
        context: dict,
        antibody: dict,
        antibody_name: str,
        candidate_ids: list[str],
        pdb_results: dict,
        heuristic_record: dict,
        require_name_evidence: bool,
        structure_ids: set[str] | None = None,
    ) -> dict | None:
        summary = self._summarize_pdb_candidates_for_llm(
            antibody_name,
            candidate_ids,
            pdb_results,
            require_name_evidence=require_name_evidence,
            structure_ids=structure_ids,
        )
        if not summary["candidates"]:
            return None
        user_msg = self.pdb_postprocess_user.format(
            PAPER_ID=context.get("paper_id", ""),
            ANTIBODY_NAME=antibody_name,
            ANTIBODY_JSON=json.dumps(antibody, ensure_ascii=False, indent=2),
            HEURISTIC_JSON=json.dumps(heuristic_record, ensure_ascii=False, indent=2),
            CANDIDATE_PDB_CODES=", ".join(candidate_ids),
            PDB_SUMMARY_JSON=json.dumps(summary, ensure_ascii=False, indent=2),
        )
        try:
            resp = await self.llm.chat(
                system=self.pdb_postprocess_system,
                user=user_msg,
                model=self.pdb_postprocess_model,
                temperature=self.pdb_postprocess_temperature,
                max_tokens=self.pdb_postprocess_max_tokens,
                response_format="json",
                trace_fields={
                    "paper_id": context.get("paper_id"),
                    "phase": context.get("current_phase"),
                    "agent": self.name,
                    "antibody_name": antibody_name,
                    "candidate_pdb_count": len(candidate_ids),
                },
            )
            payload = self.llm.parse_json_response(resp.content)
            return self._normalize_pdb_llm_record(payload, antibody_name, candidate_ids, heuristic_record)
        except Exception as exc:
            self.logger.warning(
                "PDB LLM post-process failed for %s (%s); using heuristic record. Error: %s",
                antibody_name,
                ",".join(candidate_ids),
                exc,
            )
            return None

    def _summarize_pdb_candidates_for_llm(
        self,
        antibody_name: str,
        candidate_ids: list[str],
        pdb_results: dict,
        require_name_evidence: bool,
        structure_ids: set[str] | None = None,
    ) -> dict:
        candidates = []
        for code in candidate_ids:
            pdb_result = pdb_results.get(code)
            if not pdb_result:
                continue
            score = self._pdb_candidate_score(pdb_result, antibody_name)
            if require_name_evidence and score[0] == 0 and code not in (structure_ids or set()):
                continue
            candidate = {
                "pdb_id": code,
                "title": str(((pdb_result.get("data") or {}).get("struct") or {}).get("title", "")),
                "keywords": str(((pdb_result.get("data") or {}).get("struct_keywords") or {}).get("text", "")),
                "candidate_score": {
                    "name_score": score[0],
                    "chain_score": score[1],
                    "total_len": score[2],
                },
                "heuristic_best_sequences": {},
                "fasta_entries": [],
            }
            for chain_name in ("heavy", "light"):
                entry = self._select_pdb_chain_entry(pdb_result, chain_name)
                sequence = APIClient.extract_variable_domain_from_chain((entry or {}).get("sequence", ""), chain_name)
                if sequence:
                    candidate["heuristic_best_sequences"][chain_name] = {
                        "sequence": sequence,
                        "source_description": str((entry or {}).get("description", "")),
                    }
            for entry in (pdb_result.get("fasta_entries") or [])[: self.pdb_postprocess_max_fasta_entries]:
                raw_sequence = str(entry.get("sequence", ""))
                candidate["fasta_entries"].append(
                    {
                        "chain_id": str(entry.get("chain_id", "")),
                        "chain_role": str(entry.get("chain_role", "")),
                        "description": str(entry.get("description", "")),
                        "chain_label": str(entry.get("chain_label", "")),
                        "length": len(raw_sequence),
                        "heavy_variable_guess": APIClient.extract_variable_domain_from_chain(raw_sequence, "heavy"),
                        "light_variable_guess": APIClient.extract_variable_domain_from_chain(raw_sequence, "light"),
                    }
                )
            candidates.append(candidate)
        return {"antibody_name": antibody_name, "candidates": candidates}

    def _normalize_pdb_llm_record(
        self,
        payload,
        antibody_name: str,
        candidate_ids: list[str],
        heuristic_record: dict,
    ) -> dict | None:
        if not isinstance(payload, dict):
            return None
        record = {"mAb": antibody_name}
        structure = str(payload.get("Structure", "") or "").strip().upper()
        if structure and structure in candidate_ids:
            record["Structure"] = structure
        elif heuristic_record.get("Structure"):
            record["Structure"] = heuristic_record.get("Structure")

        for src_key, dst_key, min_len in (
            ("VH_sequence", "VH_sequence", 80),
            ("VL_sequence", "VL_sequence", 80),
            ("CDRH3", "CDRH3", 5),
        ):
            value = APIClient.normalize_protein_sequence(str(payload.get(src_key, "") or ""))
            if value and len(value) >= min_len:
                record[dst_key] = value

        if not record.get("CDRH3") and record.get("VH_sequence"):
            cdrh3 = self.client.extract_cdrh3_from_variable_region(record["VH_sequence"])
            if cdrh3:
                record["CDRH3"] = cdrh3
        return record if len(record) > 1 else None

    def _merge_pdb_backfill_records(
        self,
        antibody_name: str,
        candidate_ids: list[str],
        heuristic_record: dict | None,
        llm_record: dict | None,
    ) -> dict:
        record = {"mAb": antibody_name}
        for source in (heuristic_record or {}, llm_record or {}):
            for key in ("Structure", "VH_sequence", "VL_sequence", "CDRH3"):
                value = source.get(key)
                if value:
                    record[key] = value
        if not record.get("CDRH3") and record.get("VH_sequence"):
            cdrh3 = self.client.extract_cdrh3_from_variable_region(record["VH_sequence"])
            if cdrh3:
                record["CDRH3"] = cdrh3
        if len(record) > 1:
            record["_api_source_ids"] = ",".join(candidate_ids)
            record["_api_source_kind"] = "pdb"
        return record
