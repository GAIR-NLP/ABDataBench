"""Biological validation helpers adapted from seq-extraction/scripts/bio-validate.py."""

import re
from collections import Counter

STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")
AMBIGUOUS_AA = {'B': 'D/N', 'J': 'I/L', 'O': 'Pyrrolysine', 'U': 'Selenocysteine', 'X': 'Any', 'Z': 'E/Q'}

# Fuzzy key aliases
CDRH3_KEYS = ['CDRH3_Sequence', 'CDRH3', 'cdrh3', 'CDR_H3', 'HCDR3', 'heavy_cdr3']
CDRL3_KEYS = ['CDRL3_Sequence', 'CDRL3', 'cdrl3', 'CDR_L3', 'LCDR3', 'light_cdr3']
VH_SEQ_KEYS = ['vh_sequence_aa', 'VH_sequence', 'vh_seq', 'VH_aa', 'heavy_chain_sequence']
VL_SEQ_KEYS = ['vl_sequence_aa', 'VL_sequence', 'vl_seq', 'VL_aa', 'light_chain_sequence']
AB_NAME_KEYS = ['Antibody_Name', 'antibody_name', 'name', 'mAb', 'clone']
AB_TYPE_KEYS = ['Antibody_Type', 'antibody_type', 'type', 'isotype']
EXPERIMENT_KEYS = ['Experiment', 'Experiment_Method', 'experiment']
REF_SOURCE_KEYS = ['Reference_Source', 'reference_source', 'Reference']
GERMLINE_VH_KEYS = ['vh_sequence_aa', 'VH_germline', 'germline_vh']
GERMLINE_VL_KEYS = ['vl_sequence_aa', 'VL_germline', 'germline_vl']

FIELD_NAME_CORRECTIONS = {
    'Experiment_Method': 'Experiment',
    'Experiment_value': 'Binding_Kinetics_KD',
    'Affinity_nM': 'Binding_Kinetics_KD',
    'PK_Source': 'source',
    'PK_source': 'source',
    'External_Database_ID': 'Structure',
    'Reference_source': 'Reference_Source',
    'VH_Germline': 'vh_sequence_aa',
    'VL_Germline': 'vl_sequence_aa',
}


def _fuzzy_get(entry, keys, default=None):
    for k in keys:
        if k in entry:
            v = entry[k]
            if isinstance(v, dict):
                return v.get('value', v.get('sequence', default))
            return v
    return default


def _fuzzy_get_nested(entry, keys, nested_key, default=None):
    for k in keys:
        if k in entry:
            v = entry[k]
            if isinstance(v, dict) and nested_key in v:
                return v[nested_key]
    return default


class BioValidator:
    """Biological validation engine."""

    def validate_antibody(self, ab_entry: dict) -> dict:
        ab_name = _fuzzy_get(ab_entry, AB_NAME_KEYS, 'Unknown')
        checks = []
        checks.extend(self._validate_field_names(ab_entry))
        checks.extend(self._validate_required_fields(ab_entry))

        lc_subtype = self._detect_light_chain_subtype(ab_entry)

        cdrh3 = _fuzzy_get(ab_entry, CDRH3_KEYS)
        checks.extend(self._validate_aa_chars(cdrh3, 'CDRH3'))
        checks.extend(self._validate_cdr3_length(cdrh3, 'CDRH3', 'H'))
        checks.extend(self._validate_cdr3_anchors(cdrh3, 'CDRH3', 'H'))

        cdrl3 = _fuzzy_get(ab_entry, CDRL3_KEYS)
        checks.extend(self._validate_aa_chars(cdrl3, 'CDRL3'))
        checks.extend(self._validate_cdr3_length(cdrl3, 'CDRL3', 'L'))
        checks.extend(self._validate_cdr3_anchors(cdrl3, 'CDRL3', 'L', lc_subtype))

        vh = _fuzzy_get(ab_entry, VH_SEQ_KEYS)
        checks.extend(self._validate_variable_region(vh, 'VH', 'H'))
        vl = _fuzzy_get(ab_entry, VL_SEQ_KEYS)
        checks.extend(self._validate_variable_region(vl, 'VL', 'L'))

        checks.extend(self._validate_germline_info(ab_entry))
        checks.extend(self._validate_antibody_type(ab_entry))
        checks.extend(self._validate_experiment_methods(ab_entry))
        checks.extend(self._validate_germline_identity_present(ab_entry))

        counters = Counter(c['status'] for c in checks)
        return {
            'antibody': ab_name,
            'master_id': ab_entry.get('Master_ID'),
            'checks': checks,
            'summary': {k: counters.get(k, 0) for k in ['pass', 'warn', 'fail', 'skip', 'info']},
        }

    def detect_duplicates(self, skeleton: list) -> list:
        seq_map = {}
        for ab in skeleton:
            name = _fuzzy_get(ab, AB_NAME_KEYS, 'Unknown')
            for keys, field in [(CDRH3_KEYS, 'CDRH3'), (CDRL3_KEYS, 'CDRL3'),
                                (VH_SEQ_KEYS, 'VH'), (VL_SEQ_KEYS, 'VL')]:
                seq = _fuzzy_get(ab, keys)
                if seq and seq not in ('N/A', 'null', 'None', ''):
                    seq_map.setdefault(seq.upper().replace(' ', ''), []).append((name, field))
        return [
            {'check': 'duplicate_sequence', 'status': 'warn',
             'message': f"Duplicate: {', '.join(f'{n}:{f}' for n, f in entries)} share {seq[:20]}...",
             'antibodies': [n for n, _ in entries]}
            for seq, entries in seq_map.items() if len(entries) > 1
        ]

    # ── Private validators ──

    def _validate_aa_chars(self, seq, name):
        if not seq or seq in ('N/A', 'null', 'None', ''):
            return [{'check': f'{name}_aa_chars', 'status': 'skip', 'message': f'{name}: empty/N/A'}]
        seq_upper = seq.upper().replace(' ', '').replace('-', '')
        bad = set(seq_upper) - STANDARD_AA
        if bad:
            return [{'check': f'{name}_aa_chars', 'status': 'fail',
                     'message': f'{name}: non-standard AA: {", ".join(sorted(bad))}'}]
        return [{'check': f'{name}_aa_chars', 'status': 'pass',
                 'message': f'{name}: standard AA only ({len(seq_upper)} aa)'}]

    def _validate_cdr3_length(self, seq, name, chain):
        if not seq or seq in ('N/A', 'null', 'None', ''):
            return []
        length = len(seq.upper().replace(' ', '').replace('-', ''))
        lo, hi = (5, 30) if chain == 'H' else (5, 18)
        ok = lo <= length <= hi
        return [{'check': f'{name}_length', 'status': 'pass' if ok else 'warn',
                 'message': f'{name}: {length} aa {"OK" if ok else "out of"} range ({lo}-{hi})'}]

    def _validate_cdr3_anchors(self, seq, name, chain, lc_subtype='auto'):
        if not seq or len(seq) < 2 or seq in ('N/A', 'null', 'None', ''):
            return []
        s = seq.upper().replace(' ', '').replace('-', '')
        results = []
        results.append({'check': f'{name}_n_anchor',
                        'status': 'pass' if s[0] == 'C' else 'warn',
                        'message': f'{name}: N-term {"C OK" if s[0] == "C" else s[0] + " (expected C)"}'})
        last = s[-1]
        if chain == 'H':
            results.append({'check': f'{name}_c_anchor',
                            'status': 'pass' if last == 'W' else 'warn',
                            'message': f'{name}: C-term {"W OK" if last == "W" else last + " (expected W)"}'})
        elif chain == 'L':
            ok = last in ('F', 'V', 'I', 'L', 'T')
            results.append({'check': f'{name}_c_anchor',
                            'status': 'pass' if ok else 'warn',
                            'message': f'{name}: C-term {last} {"OK" if ok else "(expected F/V/I/L/T)"}'})
        return results

    def _validate_variable_region(self, seq, name, chain):
        if not seq or seq in ('N/A', 'null', 'None', ''):
            return [{'check': f'{name}_vregion', 'status': 'skip', 'message': f'{name}: not provided'}]
        length = len(seq.upper().replace(' ', '').replace('-', ''))
        lo, hi = (110, 135) if chain == 'H' else (105, 120)
        if lo <= length <= hi:
            return [{'check': f'{name}_vregion_length', 'status': 'pass',
                     'message': f'{name}: {length} aa normal ({lo}-{hi})'}]
        # Grossly abnormal lengths indicate garbled/truncated sequences (e.g.
        # from multi-column patent tables).  Escalate to fail so the reviewer
        # triggers a retry instead of silently accepting.
        fail_lo, fail_hi = (90, 160) if chain == 'H' else (85, 145)
        if length < fail_lo or length > fail_hi:
            return [{'check': f'{name}_vregion_length', 'status': 'fail',
                     'message': f'{name}: {length} aa far outside normal ({lo}-{hi}), possible garbled sequence'}]
        return [{'check': f'{name}_vregion_length', 'status': 'warn',
                 'message': f'{name}: {length} aa outside normal ({lo}-{hi})'}]

    def _validate_germline_info(self, entry):
        results = []
        for name, keys in [('VH_germline', GERMLINE_VH_KEYS), ('VL_germline', GERMLINE_VL_KEYS)]:
            g = _fuzzy_get_nested(entry, keys, 'germline')
            if not g:
                continue
            m = re.search(r'(\d+\.?\d*)\s*%', g)
            if m:
                val = float(m.group(1))
                if val < 80:
                    results.append({'check': f'{name}_identity', 'status': 'warn',
                                    'message': f'{name}: identity {val}% < 80%'})
                else:
                    results.append({'check': f'{name}_identity', 'status': 'pass',
                                    'message': f'{name}: identity {val}% OK'})
            # Cross-check chain type
            v_gene = re.search(r'((?:IG)?[HKL]?V\d+-\d+)', g)
            if v_gene:
                gene = v_gene.group(1)
                if 'VH' in name and any(lc in gene for lc in ['KV', 'LV', 'IGKV', 'IGLV']):
                    results.append({'check': f'{name}_chain_mismatch', 'status': 'fail',
                                    'message': f'{name}: heavy field has light chain germline {gene}'})
                elif 'VL' in name and ('HV' in gene or 'IGHV' in gene):
                    results.append({'check': f'{name}_chain_mismatch', 'status': 'fail',
                                    'message': f'{name}: light field has heavy chain germline {gene}'})
        return results

    def _detect_light_chain_subtype(self, entry):
        g = _fuzzy_get_nested(entry, GERMLINE_VL_KEYS, 'germline', '')
        if not g:
            g = str(_fuzzy_get(entry, ['VJ_Light', 'vj_light'], ''))
        gl = g.lower()
        if any(k in gl for k in ['igkv', 'vk', 'kappa', 'igkj', 'jk']):
            return 'kappa'
        if any(k in gl for k in ['iglv', 'lambda', 'iglj', 'jl']):
            return 'lambda'
        return 'auto'

    def _validate_field_names(self, ab):
        return [{'check': 'field_name', 'status': 'warn',
                 'message': f'Field "{k}" should be "{v}"'}
                for k, v in FIELD_NAME_CORRECTIONS.items() if k in ab]

    def _validate_required_fields(self, ab):
        required = ['Antibody_Name', 'Antibody_Type', 'Target_Name', 'Experiment',
                     'CDRH3_Sequence', 'vh_sequence_aa', 'vl_sequence_aa', 'Reference_Source']
        # Extended fields that should ideally be present (warn if missing)
        recommended = ['Binding_Kinetics_KD', 'Mechanism_of_Action', 'source']
        results = []
        for f in required:
            if f not in ab:
                alias_found = False
                for alias_keys in [EXPERIMENT_KEYS, REF_SOURCE_KEYS]:
                    if any(a in ab for a in alias_keys):
                        alias_found = True
                        break
                if not alias_found:
                    results.append({'check': 'missing_field', 'status': 'warn',
                                    'message': f'Missing field: {f}'})
        for f in recommended:
            if f not in ab or not ab[f] or ab[f] in ('N/A', 'null', 'None', ''):
                results.append({'check': 'missing_recommended', 'status': 'info',
                                'message': f'Recommended field empty: {f}'})
        return results

    def _validate_antibody_type(self, ab):
        t = _fuzzy_get(ab, AB_TYPE_KEYS)
        if not t:
            return []
        tl = t.lower()
        specific = ['igg1', 'igg2', 'igg3', 'igg4', 'igm', 'iga',
                     'vhh', 'nanobody', 'scfv', 'fab', 'bispecific']
        has_specific = any(s in tl for s in specific)
        vague = ['单克隆抗体', '中和抗体', 'monoclonal antibody']
        is_vague = any(p in tl for p in vague) and not has_specific
        if is_vague:
            return [{'check': 'antibody_type_specificity', 'status': 'warn',
                     'message': f'Antibody_Type "{t}" too vague, need specific subtype'}]
        return []

    def _validate_experiment_methods(self, ab):
        experiment = str(_fuzzy_get(ab, EXPERIMENT_KEYS, '') or '')
        if not experiment:
            return []
        lowered = experiment.lower()
        banned = []
        banned_patterns = {
            'Western blot': r'western blot|\bwb\b',
            'crystallography': r'x-ray|xray|cryo-?em|crystallography',
            'sequencing': r'sequencing',
            'sorting/gating': r'sorting|gating|expression qc',
            'challenge/in vivo model': r'challenge|mouse model|in vivo',
            'immunoprecipitation/LC-MS': r'immunoprecipitation|lc-?ms|mass spectrometry',
        }
        for label, pattern in banned_patterns.items():
            if re.search(pattern, lowered):
                banned.append(label)
        if not banned:
            return []
        return [{
            'check': 'experiment_scope',
            'status': 'warn',
            'message': f'Experiment contains peripheral/non-direct methods: {", ".join(banned)}',
        }]

    def _validate_germline_identity_present(self, ab):
        results = []
        for name, keys in [('VH germline', GERMLINE_VH_KEYS), ('VL germline', GERMLINE_VL_KEYS)]:
            g = _fuzzy_get_nested(ab, keys, 'germline')
            if not g:
                continue
            has_pct = bool(re.search(r'\d+\.?\d*\s*%', g))
            results.append({
                'check': f'{name}_identity_present',
                'status': 'pass' if has_pct else 'warn',
                'message': f'{name}: {"has" if has_pct else "MISSING"} identity% → "{g}"',
            })
        return results
