"""Unified OpenAI-compatible LLM client."""

import json
import asyncio
import logging
import random
import re
import time
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    finish_reason: str = ""

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class RateLimiter:
    """Token-bucket-style rate limiter."""

    def __init__(self, rpm: int = 500, tpm: int = 2_000_000, max_concurrent: int = 50):
        self.rpm = rpm
        self.tpm = tpm
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._request_times: list[float] = []
        self._token_usage: list[tuple[float, int]] = []
        self._lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int = 4000):
        await self.semaphore.acquire()
        async with self._lock:
            now = time.monotonic()
            self._request_times = [t for t in self._request_times if now - t < 60]
            self._token_usage = [(t, n) for t, n in self._token_usage if now - t < 60]
            if len(self._request_times) >= self.rpm:
                wait = 60 - (now - self._request_times[0])
                if wait > 0:
                    await asyncio.sleep(wait)
            current_tpm = sum(n for _, n in self._token_usage)
            if current_tpm + estimated_tokens > self.tpm:
                if self._token_usage:
                    wait = 60 - (now - self._token_usage[0][0])
                    if wait > 0:
                        await asyncio.sleep(wait)
            self._request_times.append(time.monotonic())

    def release(self, actual_tokens: int = 0):
        self._token_usage.append((time.monotonic(), actual_tokens))
        self.semaphore.release()


class LLMClient:
    """Unified OpenAI-compatible LLM client."""

    def __init__(self, config, rate_limiter: Optional[RateLimiter] = None):
        self.api_base = config.llm_api_base.rstrip("/")
        self.api_key = config.llm_api_key
        self.model = config.llm_model
        self.timeout = getattr(config, "llm_timeout", 600)
        self.use_bearer_auth = getattr(config, "llm_use_bearer_auth", True)
        self.disable_proxy = getattr(config, "llm_disable_proxy", False)
        self.enable_thinking = getattr(config, "llm_enable_thinking", False)
        self.rate_limiter = rate_limiter
        self.mock_mode = getattr(config, "mock_llm", False)
        self.mock_latency_ms = getattr(config, "mock_llm_latency_ms", 700)
        self.mock_jitter_ms = getattr(config, "mock_llm_jitter_ms", 250)
        self.tracer = getattr(config, "trace_recorder", None)
        self._total_calls = 0
        self._total_tokens = 0

    async def chat(
        self,
        system: str,
        user: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 8192,
        response_format: Optional[str] = None,
        retry_count: int = 3,
        trace_fields: Optional[dict] = None,
    ) -> LLMResponse:
        messages = [
            {"role": "user", "content": user},
        ]
        return await self.chat_messages(
            system=system,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            retry_count=retry_count,
            trace_fields=trace_fields,
        )

    async def chat_messages(
        self,
        system: str,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 8192,
        response_format: Optional[str] = None,
        retry_count: int = 3,
        trace_fields: Optional[dict] = None,
    ) -> LLMResponse:
        model = model or self.model
        payload = self._build_payload(
            model=model,
            system=system,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        headers = self._build_headers()
        trace_fields = trace_fields or {}
        span_id = None
        if self.tracer:
            span_id = self.tracer.start_span(
                "tool",
                "llm.chat",
                tool="llm.chat",
                model=model,
                request_chars=len(system) + sum(len(str(m.get("content", ""))) for m in messages),
                **trace_fields,
            )

        if self.mock_mode:
            user_text = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") == "user")
            result = await self._mock_chat(system, user_text, model)
            if self.tracer:
                self.tracer.end_span(
                    span_id,
                    status="success",
                    total_tokens=result.total_tokens,
                    finish_reason=result.finish_reason,
                )
            return result

        for attempt in range(retry_count):
            if self.rate_limiter:
                await self.rate_limiter.acquire()
            try:
                async with httpx.AsyncClient(timeout=self.timeout, trust_env=not self.disable_proxy) as client:
                    resp = await client.post(
                        f"{self.api_base}/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    if resp.status_code == 429:
                        wait = 2 ** (attempt + 1)
                        logger.warning(f"Rate limited, retrying in {wait}s...")
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    data = resp.json()

                usage = data.get("usage", {})
                choice = data["choices"][0]
                result = LLMResponse(
                    content=choice["message"]["content"],
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    model=data.get("model", model),
                    finish_reason=choice.get("finish_reason", ""),
                )
                self._total_calls += 1
                self._total_tokens += result.total_tokens
                if self.tracer:
                    self.tracer.end_span(
                        span_id,
                        status="success",
                        total_tokens=result.total_tokens,
                        finish_reason=result.finish_reason,
                        http_status=resp.status_code,
                    )
                return result
            except httpx.HTTPStatusError as e:
                if self.tracer and attempt == retry_count - 1:
                    self.tracer.end_span(
                        span_id,
                        status="error",
                        http_status=e.response.status_code,
                        error=str(e),
                    )
                if attempt < retry_count - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"HTTP {e.response.status_code}, retry in {wait}s")
                    await asyncio.sleep(wait)
                else:
                    raise
            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                if self.tracer and attempt == retry_count - 1:
                    self.tracer.end_span(span_id, status="error", error=str(e))
                if attempt < retry_count - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Connection error: {e}, retry in {wait}s")
                    await asyncio.sleep(wait)
                else:
                    raise
            finally:
                if self.rate_limiter:
                    self.rate_limiter.release()

        raise RuntimeError(f"LLM call failed after {retry_count} retries")

    def _build_payload(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        response_format: Optional[str],
    ) -> dict:
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": self.enable_thinking},
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _build_headers(self) -> dict:
        return {
            "Authorization": self._auth_header_value(self.api_key),
            "Content-Type": "application/json",
        }

    def _auth_header_value(self, api_key: str) -> str:
        if self.use_bearer_auth and not api_key.startswith("Bearer "):
            return f"Bearer {api_key}"
        return api_key

    async def _mock_chat(self, system: str, user: str, model: str) -> LLMResponse:
        base = self.mock_latency_ms / 1000
        jitter = random.uniform(0, max(self.mock_jitter_ms, 0)) / 1000
        size_penalty = min(len(user) / 50000, 1.2)
        await asyncio.sleep(base + jitter + size_penalty)

        content = self._mock_content(system, user)
        tokens = max(128, len(user) // 12)
        result = LLMResponse(
            content=content,
            input_tokens=tokens,
            output_tokens=max(64, len(content) // 6),
            model=f"mock::{model}",
            finish_reason="stop",
        )
        self._total_calls += 1
        self._total_tokens += result.total_tokens
        return result


    def _mock_content(self, system: str, user: str) -> str:
        if "[Reduction Task]:" in user:
            return self._mock_reducer_response(user)
        if "[Paper Focus Analysis Task]" in user:
            return self._mock_paper_focus_response(user)
        if "[Paper ID]:" in user:
            return self._mock_skeleton_response(user)
        if "Validation Failures" in user:
            return "- acceptable: mock reviewer found no field-level correction beyond validation warnings."
        return json.dumps({"ok": True}, ensure_ascii=False)

    def _mock_reducer_response(self, user: str) -> str:
        match = re.search(r"\[Chunk Text\]:\n(.*)", user, re.DOTALL)
        chunk_text = match.group(1).strip() if match else user
        blocks = [block.strip() for block in re.split(r"\n\s*\n+", chunk_text) if block.strip()]
        keep_blocks = []
        drop_section = False
        low_value_headings = {
            "# references",
            "# bibliography",
            "# acknowledgements",
            "# acknowledgments",
            "# author contributions",
            "# competing interests",
            "# conflict of interest",
            "# conflicts of interest",
            "# data availability",
        }
        keep_keywords = (
            "antibody", "mab", "cdrh3", "cdrl3", "vh", "vl", "heavy chain", "light chain",
            "kd", "kon", "koff", "ec50", "ic50", "pdb", "genbank", "accession", "supplement",
            "figure", "table", "structure", "sequence", "binding", "neutralization", "![", "images/"
        )
        for block in blocks:
            lowered = block.lower()
            first_line = lowered.splitlines()[0].strip()
            if first_line in low_value_headings:
                drop_section = True
                continue
            if block.startswith("#") and first_line not in low_value_headings:
                drop_section = False
            if drop_section and not any(keyword in lowered for keyword in ("pdb", "genbank", "accession", "sequence")):
                continue
            if any(keyword in lowered for keyword in keep_keywords):
                keep_blocks.append(block)
        filtered_text = "\n\n".join(keep_blocks).strip()
        return json.dumps(
            {
                "keep": bool(filtered_text),
                "filtered_text": filtered_text,
                "evidence_types": ["mock_filter"],
                "notes": "mock chunk filter",
            },
            ensure_ascii=False,
        )

    def _mock_skeleton_response(self, user: str) -> str:
        match = re.search(r"\[Paper ID\]:\s*([^\n]+)", user)
        paper_id = (match.group(1).strip() if match else "unknown-paper")
        name_seed = paper_id.split("-")[0].upper()
        payload = {
            paper_id: {
                "paper_id": paper_id,
                "title": f"Mock extraction for {paper_id}",
                "antibodies": [
                    {
                        "Antibody_Name": f"{name_seed}-Mock-1",
                        "Antibody_Type": "IgG1 monoclonal antibody",
                        "Antibody_Isotype": "Human IgG1",
                        "source": "Human",
                        "Target_Name": "Mock antigen",
                        "Target_Type": "Protein",
                        "Cross_Reactivity": "",
                        "Epitope": "Mock epitope",
                        "Experiment": "SPR, ELISA",
                        "Binding_Kinetics_KD": "6.91 nM",
                        "Binding_Kinetics_kon": "1.74e7 1/Ms",
                        "Binding_Kinetics_koff": "1.2e-4 1/s",
                        "Binding_EC50": "0.5 nM",
                        "Mechanism_of_Action": "Neutralization",
                        "Quantitative_Metric": "IC50 = 0.05 ug/mL",
                        "Structure": "",
                        "CDRH3_Sequence": "CARDRSTGYYYYFDYW",
                        "vh_sequence_aa": "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISSGGGSTYYADSVKGRFTISRDNAKNTLYLQMNSLRAEDTAVYYCARDRSTGYYYYFDYWGQGTLVTVSS",
                        "vl_sequence_aa": "DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYNSYPLTFGQGTKVEIK",
                        "Thermal_Stability_Tm": "",
                        "In_Vivo_Half_Life": "",
                        "In_Vivo_Efficacy": "",
                        "Reference_Source": paper_id,
                    }
                ],
            }
        }
        return json.dumps(payload, ensure_ascii=False)

    def _mock_paper_focus_response(self, user: str) -> str:
        likely_core = []
        for match in re.findall(r'"priority_antibody_names":\s*\[(.*?)\]', user, re.DOTALL):
            likely_core.extend(re.findall(r'"([^"]+)"', match))
        payload = {
            "llm_focus_summary": (
                "Treat this as a hard paper: keep extraction anchored to table or panel-local evidence, "
                "split records when target or condition changes, and keep comparator-style names out unless they have local data."
            ),
            "likely_core_antibodies": likely_core[:4],
            "likely_reference_only_antibodies": [],
            "record_split_alerts": [
                "split when the same antibody has target-specific or condition-specific quantitative values",
                "keep KD/kon/koff together only when they come from the same local evidence row or panel",
            ],
            "sequence_source_priority": [
                "prefer supplementary or table-local sequence rows before narrative mentions",
                "prefer accession-backed recovery over partial image fragments when full sequence is absent",
            ],
            "recommended_order": [
                "start from the most local table or supplementary rows",
                "then bind figure-caption values only when the antibody-target-value mapping is explicit",
                "use narrative text only as a fallback",
            ],
            "local_binding_warnings": [
                "do not broadcast structure or epitope claims across targets or constructs",
                "do not treat germline, MRCA, or control antibodies as core records without local quantitative evidence",
            ],
        }
        return json.dumps(payload, ensure_ascii=False)

    def parse_json_response(self, text: str) -> list | dict:
        """Parse JSON from an LLM response with defensive truncation repair."""
        cleaned = text.strip()
        # Remove Markdown fences.
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        # Try direct parsing.
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        # Try to extract a JSON array or object from surrounding text.
        for start_char, end_char in [("[", "]"), ("{", "}")]:
            start = cleaned.find(start_char)
            end = cleaned.rfind(end_char)
            if start != -1 and end > start:
                try:
                    return json.loads(cleaned[start:end + 1])
                except json.JSONDecodeError:
                    continue
        # Repair truncated output by closing JSON structures where possible.
        repaired = self._repair_truncated_json(cleaned)
        if repaired is not None:
            return repaired
        raise ValueError(f"Cannot parse JSON from LLM response: {cleaned[:200]}...")

    @staticmethod
    def _repair_truncated_json(text: str):
        """Attempt to repair truncated JSON by closing brackets and quotes."""
        # Find the start of a JSON object or array.
        start = -1
        for i, ch in enumerate(text):
            if ch in ('{', '['):
                start = i
                break
        if start == -1:
            return None

        fragment = text[start:]
        # Remove incomplete trailing key/value fragments by backing up to the
        # last complete object or array element.
        for trim_pat in [
            # Trim after the last complete "}," or "}]" fragment.
            r'(\}\s*,)\s*\{[^}]*$',
            r'(\}\s*\])\s*[^]]*$',
        ]:
            import re
            m = re.search(trim_pat, fragment, re.DOTALL)
            if m:
                fragment = fragment[:m.end(1)]
                break

        # Track unclosed brackets.
        stack = []
        in_string = False
        escape = False
        for ch in fragment:
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in ('{', '['):
                stack.append(ch)
            elif ch == '}' and stack and stack[-1] == '{':
                stack.pop()
            elif ch == ']' and stack and stack[-1] == '[':
                stack.pop()

        if in_string:
            fragment += '"'
        # Close unclosed brackets.
        closers = {'[': ']', '{': '}'}
        for bracket in reversed(stack):
            fragment += closers[bracket]

        try:
            return json.loads(fragment)
        except json.JSONDecodeError:
            return None

    @property
    def stats(self) -> dict:
        return {"total_calls": self._total_calls, "total_tokens": self._total_tokens}
