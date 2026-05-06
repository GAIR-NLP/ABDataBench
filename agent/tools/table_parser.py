"""Table parsing helpers adapted from seq-extraction/scripts/table-extract.py."""

import re
from html.parser import HTMLParser


SEMANTIC_COLUMNS = [
    ('mAb', ['mab', 'antibody', 'clone', 'name'], False),
    ('VDJ_Heavy', ['vdj heavy', 'vdj_heavy', 'v(d)j heavy', 'heavy chain v', 'vh/dh/jh'], False),
    ('VJ_Light', ['vj light', 'vj_light', 'v(j) light', 'light chain v', 'vk/jk', 'vl/jl'], False),
    ('CDRH3', ['cdrh3', 'cdr-h3', 'cdr h3', 'hcdr3', 'heavy cdr3'], False),
    ('CDRL3', ['cdrl3', 'cdr-l3', 'cdr l3', 'lcdr3', 'light cdr3', 'cdr-k3'], False),
    ('VH_identity_pct', ['vh identity', 'vh_identity', 'v region identity', 'vh v region'], False),
    ('VL_identity_pct', ['vl identity', 'vl_identity', 'vk identity', 'vl v region'], False),
    ('VH_sequence', ['vh sequence', 'heavy chain sequence', 'vh_aa', 'vh_seq'], False),
    ('VL_sequence', ['vl sequence', 'light chain sequence', 'vl_aa', 'vl_seq', 'vk sequence'], False),
    ('Isotype', ['isotype', 'subclass', 'igg'], False),
    ('Target', ['target', 'antigen', 'specificity'], False),
    ('KD', ['kd', 'affinity'], False),
    ('EC50', ['ec50'], False),
    ('IC50', ['ic50'], False),
]


class _HTMLTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = []
        self.current_row = []
        self.current_data = ''
        self.in_cell = False
        self.in_table = False
        self.current_colspan = 1
        self.current_rowspan = 1
        # {col_index: [remaining_rows, cell_value]}
        self.pending_rowspans: dict[int, list] = {}

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == 'table':
            self.in_table = True
            self.current_table = []
            self.pending_rowspans = {}
        elif tag == 'tr':
            self.current_row = []
            self._col_cursor = 0
        elif tag in ('td', 'th'):
            self.in_cell = True
            self.current_data = ''
            self.current_colspan = 1
            self.current_rowspan = 1
            for n, v in attrs:
                nl = n.lower()
                if nl == 'colspan' and v:
                    try:
                        self.current_colspan = int(v)
                    except ValueError:
                        pass
                elif nl == 'rowspan' and v:
                    try:
                        self.current_rowspan = int(v)
                    except ValueError:
                        pass
            # Before placing this cell, skip over columns occupied by rowspans
            self._skip_pending_cols()

    def _skip_pending_cols(self):
        """Inject pending rowspan cells at the current cursor position."""
        while self._col_cursor in self.pending_rowspans:
            entry = self.pending_rowspans[self._col_cursor]
            self.current_row.append(entry[1])
            entry[0] -= 1
            if entry[0] <= 0:
                del self.pending_rowspans[self._col_cursor]
            self._col_cursor += 1

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ('td', 'th'):
            self.in_cell = False
            cell = self.current_data.strip()
            for _ in range(self.current_colspan):
                self.current_row.append(cell)
                if self.current_rowspan > 1:
                    self.pending_rowspans[self._col_cursor] = [
                        self.current_rowspan - 1, cell
                    ]
                self._col_cursor += 1
                # After placing, skip any pending columns
                self._skip_pending_cols()
            self.current_colspan = 1
            self.current_rowspan = 1
        elif tag == 'tr':
            # Flush any trailing pending rowspan cells
            if hasattr(self, '_col_cursor'):
                self._skip_pending_cols()
            if self.current_row:
                self.current_table.append(self.current_row)
        elif tag == 'table':
            self.in_table = False
            if self.current_table:
                self.tables.append(self.current_table)

    def handle_data(self, data):
        if self.in_cell:
            self.current_data += data

    def handle_entityref(self, name):
        if self.in_cell:
            m = {'nbsp': ' ', 'lt': '<', 'gt': '>', 'amp': '&', 'quot': '"'}
            self.current_data += m.get(name, f'&{name};')

    def handle_charref(self, name):
        if self.in_cell:
            try:
                self.current_data += chr(int(name[1:], 16) if name.startswith('x') else int(name))
            except (ValueError, OverflowError):
                self.current_data += f'&#{name};'


class TableParser:
    """HTML and Markdown table parser with semantic column mapping."""

    _CHAIN_LABEL_PATTERNS = (
        re.compile(r'^\s*(.+?)\s*\(\s*(VH|VL|heavy|light)\s*\)\s*$', re.IGNORECASE),
        re.compile(r'^\s*(.+?)\s+(VH|VL|heavy|light)\s*$', re.IGNORECASE),
    )

    def extract_html_tables(self, text: str) -> list:
        parser = _HTMLTableParser()
        for block in re.findall(r'<table[^>]*>.*?</table>', text, re.DOTALL | re.IGNORECASE):
            parser.feed(block)
        return parser.tables

    def extract_markdown_tables(self, text: str) -> list:
        lines = text.split('\n')
        tables, current, in_table = [], [], False
        for line in lines:
            stripped = line.strip()
            is_pipe = '|' in stripped and stripped.startswith('|')
            is_sep = bool(re.match(r'^\|[\s:]*-{2,}[\s:]*(\|[\s:]*-{2,}[\s:]*)+\|?\s*$', stripped))
            if is_pipe:
                if is_sep:
                    if in_table:
                        continue
                    elif current:
                        in_table = True
                        continue
                else:
                    cells = [c.strip() for c in stripped.split('|')]
                    if cells and cells[0] == '':
                        cells = cells[1:]
                    if cells and cells[-1] == '':
                        cells = cells[:-1]
                    current.append(cells)
                    in_table = True
            else:
                if in_table and len(current) >= 2:
                    tables.append(current)
                current, in_table = [], False
        if in_table and len(current) >= 2:
            tables.append(current)
        return tables

    def map_columns_semantic(self, headers: list[str]) -> dict:
        mapping = {}
        used = set()
        headers_lower = [h.lower().strip() for h in headers]
        for i, h in enumerate(headers_lower):
            for out_key, keywords, _ in SEMANTIC_COLUMNS:
                if out_key in used:
                    continue
                if any(kw in h for kw in keywords):
                    mapping[i] = out_key
                    used.add(out_key)
                    break
        # Handle duplicate identity columns
        all_id_cols = [i for i, h in enumerate(headers_lower) if 'identity' in h or 'v region' in h]
        if 'VL_identity_pct' not in used and len(all_id_cols) >= 2:
            mapping[all_id_cols[1]] = 'VL_identity_pct'
            used.add('VL_identity_pct')
        for i, h in enumerate(headers):
            if i not in mapping:
                mapping[i] = h.strip() or f'col_{i}'
        return mapping

    def identify_antibody_table(self, headers: list[str]) -> bool:
        kw = {'mab', 'antibody', 'cdr', 'cdrh3', 'cdrl3', 'hcdr3', 'lcdr3',
              'vh', 'vl', 'vdj', 'heavy', 'light', 'germline', 'identity',
              'sequence', 'clone', 'v region', 'isotype', 'neutrali', 'seq id'}
        text = ' '.join(h.lower() for h in headers)
        return sum(1 for k in kw if k in text) >= 2

    def table_to_records(self, table: list) -> dict:
        if len(table) < 2:
            return {'headers': table[0] if table else [], 'column_mapping': {},
                    'is_antibody_table': False, 'rows': []}
        headers = table[0]
        col_map = self.map_columns_semantic(headers)
        records = []
        for row in table[1:]:
            record = {}
            for i, cell in enumerate(row):
                record[col_map.get(i, f'col_{i}')] = cell
            records.append(record)
        return {
            'headers': headers,
            'column_mapping': {str(i): v for i, v in col_map.items()},
            'is_antibody_table': self.identify_antibody_table(headers),
            'rows': records,
        }

    # ---- amino-acid character set for fragment detection ----
    _AA_CHARS = set('ACDEFGHIKLMNPQRSTVWY')

    def _parse_chain_row_label(self, value: str):
        label = re.sub(r'\s+', ' ', str(value or '')).strip()
        if not label:
            return None
        for pattern in self._CHAIN_LABEL_PATTERNS:
            match = pattern.match(label)
            if not match:
                continue
            name = match.group(1).strip()
            raw_chain = match.group(2).strip().lower()
            chain = 'VH' if raw_chain in ('vh', 'heavy') else 'VL'
            return name, chain
        return None

    def _clean_sequence_fragment(self, value: str) -> str:
        return re.sub(r'[^A-Za-z]', '', str(value or '')).upper()

    def _is_sequence_like_fragment(self, value: str) -> bool:
        text = self._clean_sequence_fragment(value)
        if len(text) < 4:
            return False
        aa_fraction = sum(1 for c in text if c in self._AA_CHARS) / len(text)
        return aa_fraction >= 0.8

    def _row_sequence_cells(self, row: list[str]) -> list[str]:
        return [cell.strip() for cell in row[2:] if cell and cell.strip()]

    def _row_looks_like_sequence_fragment(self, row: list[str]) -> bool:
        seq_cells = self._row_sequence_cells(row)
        if len(seq_cells) < 3:
            return False
        hits = sum(1 for cell in seq_cells if self._is_sequence_like_fragment(cell))
        return hits / len(seq_cells) >= 0.6

    def _detect_sequence_fragment_table(self, table: list) -> bool:
        """Return True if table looks like a multi-cell sequence fragment table.

        Heuristics:
        - Header contains Antibody/SEQ ID cues
        - At least one data row encodes antibody + chain in column 0
        - Columns index 2+ contain predominantly AA fragments
        """
        if len(table) < 2:
            return False
        header_text = ' '.join(str(cell or '').lower() for cell in table[0])
        has_header_cues = 'seq id' in header_text and 'antibody' in header_text
        data_rows = table[1:]
        chain_matches = 0
        aa_rows = 0
        for row in data_rows:
            if not row:
                continue
            if self._parse_chain_row_label(row[0]):
                chain_matches += 1
            if self._row_looks_like_sequence_fragment(row):
                aa_rows += 1
        return has_header_cues and chain_matches >= 1 and aa_rows >= 1

    def _split_fragment_chunks(self, value: str, chunk_size: int = 10) -> list[str]:
        text = self._clean_sequence_fragment(value)
        if not text:
            return []
        return [text[idx: idx + chunk_size] for idx in range(0, len(text), chunk_size)]

    def _reconstruct_interleaved_single_row(self, row: list[str], chunk_size: int = 10) -> str:
        chunk_columns = [
            self._split_fragment_chunks(cell, chunk_size=chunk_size)
            for cell in self._row_sequence_cells(row)
        ]
        if not chunk_columns:
            return ''
        parts = []
        max_rows = max(len(chunks) for chunks in chunk_columns)
        for chunk_idx in range(max_rows):
            for chunks in chunk_columns:
                if chunk_idx < len(chunks):
                    parts.append(chunks[chunk_idx])
        return ''.join(parts)

    def _reconstruct_row_major_block(self, rows: list[list[str]]) -> str:
        parts = []
        for row in rows:
            for cell in self._row_sequence_cells(row):
                cleaned = self._clean_sequence_fragment(cell)
                if cleaned:
                    parts.append(cleaned)
        return ''.join(parts)

    def _assemble_sequence_fragment_records(self, table: list) -> list[dict]:
        """Reconstruct full VH/VL sequences from OCR-split patent tables."""
        records = []
        current_name = None
        current_chain = None
        current_rows: list[list[str]] = []

        def _flush():
            nonlocal current_name, current_chain, current_rows
            if current_name and current_rows:
                # Always use row-major (left-to-right) concatenation.
                # Patent Table B layouts store consecutive AA fragments across
                # columns; interleaved reconstruction produces scrambled output.
                seq = self._reconstruct_row_major_block(current_rows)
                if len(seq) >= 80:
                    chain_key = 'VH_sequence' if current_chain == 'VH' else 'VL_sequence'
                    records.append({
                        'mAb': current_name,
                        chain_key: seq,
                        '_source_context': (
                            f"Sequence fragment table reconstruction for {current_name} {current_chain}"
                        ),
                    })
            current_name = None
            current_chain = None
            current_rows = []

        data_rows = table[1:] if len(table) > 1 else table
        for row in data_rows:
            if not row:
                continue
            label = self._parse_chain_row_label(row[0])
            if label and self._row_looks_like_sequence_fragment(row):
                name, chain = label
                if current_name and (name != current_name or chain != current_chain):
                    _flush()
                current_name = name
                current_chain = chain
                current_rows.append(row)
            elif current_name and self._row_looks_like_sequence_fragment(row):
                current_rows.append(row)
            else:
                _flush()
        _flush()
        return records

    def extract_all_antibody_records(self, text: str) -> list[dict]:
        """Extract all antibody-table records from text."""
        all_tables = self.extract_html_tables(text) + self.extract_markdown_tables(text)
        all_records = []
        for table in all_tables:
            result = self.table_to_records(table)
            if result['is_antibody_table']:
                all_records.extend(result['rows'])
        # Second pass: detect sequence fragment tables and assemble full sequences
        for table in all_tables:
            if self._detect_sequence_fragment_table(table):
                seq_records = self._assemble_sequence_fragment_records(table)
                all_records.extend(seq_records)
        return all_records
