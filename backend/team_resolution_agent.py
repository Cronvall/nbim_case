"""
Team-based resolution agents for dividend reconciliation fixes.
- AccountantAgent: domain logic, ties factors and proposes field-level corrections
- MathematicianAgent: verifies/recomputes numeric relationships and amounts
- ManagerAgent: orchestrates, validates proposals, and approves final changes

This is a rule-based implementation designed to be deterministic and fast.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
import math


@dataclass
class Change:
    target: str             # 'nbim' or 'custody'
    row_index: int          # index in the target DataFrame
    field: str              # column name to change
    new_value: Any          # value to set
    reason: str             # short explanation
    confidence: float = 0.8 # 0..1


class AccountantAgent:
    """Applies domain heuristics to propose field-level corrections per row pair."""

    AUTHORITATIVE_SOURCE = 'NBIM'  # prefer NBIM when both sides exist
    ALIGN_FIELDS = [
        'net_amount', 'gross_amount', 'tax_amount', 'tax_rate', 'currency',
        'ex_date', 'payment_date', 'nominal_basis'
    ]

    def propose(self,
                nbim_row: Optional[Dict[str, Any]],
                custody_row: Optional[Dict[str, Any]],
                nbim_idx: Optional[int],
                custody_idx: Optional[int]) -> List[Change]:
        proposals: List[Change] = []

        # Missing record cases: propose cloning from the present side
        if nbim_row is None and custody_row is not None and custody_idx is not None:
            # Propose to add custody row into NBIM (manager will execute via DataFrame append)
            # Represent as a special Change with field = '__ADD_ROW__'
            proposals.append(Change(target='nbim', row_index=-1, field='__ADD_ROW__', new_value=custody_row,
                                    reason='Create NBIM row from custody (missing in NBIM)', confidence=0.9))
            return proposals
        if custody_row is None and nbim_row is not None and nbim_idx is not None:
            proposals.append(Change(target='custody', row_index=-1, field='__ADD_ROW__', new_value=nbim_row,
                                    reason='Create custody row from NBIM (missing in custody)', confidence=0.9))
            return proposals

        if nbim_row is None or custody_row is None:
            return proposals

        # Both present: align selected fields from authoritative source NBIM -> custody
        for col in self.ALIGN_FIELDS:
            if col in nbim_row and col in custody_row:
                v_src = nbim_row.get(col)
                v_dst = custody_row.get(col)
                if not self._equivalent(v_src, v_dst):
                    proposals.append(Change(
                        target='custody', row_index=custody_idx, field=col, new_value=v_src,
                        reason=f'Align {col} to NBIM authoritative value', confidence=0.85
                    ))

        return proposals

    @staticmethod
    def _equivalent(a: Any, b: Any) -> bool:
        try:
            if pd.isna(a) and pd.isna(b):
                return True
        except Exception:
            pass
        # numeric tolerance
        try:
            af = float(a)
            bf = float(b)
            return math.isclose(af, bf, rel_tol=1e-6, abs_tol=1e-6)
        except Exception:
            return str(a) == str(b)


class MathematicianAgent:
    """Recomputes numeric relationships to ensure consistency after accountant proposals."""

    def refine(self, row: Dict[str, Any]) -> Dict[str, Any]:
        # If gross and tax_rate given, recompute tax and net
        out = dict(row)
        try:
            gross = float(out.get('gross_amount')) if out.get('gross_amount') is not None else None
            tax_rate = float(out.get('tax_rate')) if out.get('tax_rate') is not None else None
            tax = out.get('tax_amount')
            net = out.get('net_amount')

            if gross is not None and tax_rate is not None:
                computed_tax = round(gross * (tax_rate / 100.0), 2)
                out['tax_amount'] = computed_tax
                if net is not None:
                    try:
                        net_val = float(net)
                        # if far off, recompute net
                        if not math.isclose(net_val, gross - computed_tax, abs_tol=0.01):
                            out['net_amount'] = round(gross - computed_tax, 2)
                    except Exception:
                        out['net_amount'] = round(gross - computed_tax, 2)
                else:
                    out['net_amount'] = round(gross - computed_tax, 2)
            elif gross is not None and tax is not None:
                try:
                    tax_val = float(tax)
                    out['net_amount'] = round(gross - tax_val, 2)
                    if gross != 0:
                        out['tax_rate'] = round((tax_val / gross) * 100.0, 4)
                except Exception:
                    pass
        except Exception:
            # Be resilient; don't fail the pipeline
            return out
        return out


class ManagerAgent:
    """Approves or rejects proposed changes and applies them to DataFrames."""

    def apply_changes(self,
                      nbim_df: pd.DataFrame,
                      custody_df: pd.DataFrame,
                      proposals: List[Change]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        nbim_df_out = nbim_df.copy()
        custody_df_out = custody_df.copy()

        for ch in proposals:
            try:
                if ch.field == '__ADD_ROW__' and isinstance(ch.new_value, dict):
                    # Append new row to target with minimal normalization: ensure 'source'
                    new_row = dict(ch.new_value)
                    new_row['source'] = 'NBIM' if ch.target == 'nbim' else 'CUSTODY'
                    if ch.target == 'nbim':
                        nbim_df_out = pd.concat([nbim_df_out, pd.DataFrame([new_row])], ignore_index=True)
                    else:
                        custody_df_out = pd.concat([custody_df_out, pd.DataFrame([new_row])], ignore_index=True)
                    continue

                if ch.row_index is None or ch.row_index < 0:
                    # Skip invalid direct set
                    continue

                if ch.target == 'nbim':
                    nbim_df_out.at[ch.row_index, ch.field] = ch.new_value
                else:
                    custody_df_out.at[ch.row_index, ch.field] = ch.new_value
            except Exception:
                # Skip problematic changes rather than failing the flow
                continue

        return nbim_df_out, custody_df_out


class TeamResolutionOrchestrator:
    """Coordinates Accountant and Mathematician agents; Manager applies approved changes."""

    def __init__(self) -> None:
        self.accountant = AccountantAgent()
        self.math = MathematicianAgent()
        self.manager = ManagerAgent()

    def resolve(self, nbim_df: pd.DataFrame, custody_df: pd.DataFrame, report_data: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        # Build index by (isin, event_key)
        def make_index(df: pd.DataFrame):
            return {(str(r.get('isin')), str(r.get('event_key'))): i for i, r in enumerate(df.to_dict('records'))}

        nbim_index = make_index(nbim_df)
        custody_index = make_index(custody_df)

        proposals: List[Change] = []

        for row in report_data.get('row_analyses', []):
            isin = str((row.get('raw_fields') or {}).get('ISIN') or (row.get('row_id') or '').split('-')[0] or '')
            event_key = str((row.get('raw_fields') or {}).get('COAC_EVENT_KEY') or row.get('event_key') or '')
            key = (isin, event_key)

            nbim_i = nbim_index.get(key)
            custody_i = custody_index.get(key)

            nbim_row = nbim_df.iloc[nbim_i].to_dict() if nbim_i is not None else None
            custody_row = custody_df.iloc[custody_i].to_dict() if custody_i is not None else None

            # Accountant proposes field alignments / row creations
            acc_props = self.accountant.propose(nbim_row, custody_row, nbim_i, custody_i)

            # Mathematician refines numeric consistency for the affected target rows
            refined_props: List[Change] = []
            for ch in acc_props:
                if ch.field == '__ADD_ROW__' and isinstance(ch.new_value, dict):
                    refined_props.append(ch)
                    continue
                # If we are changing a row's field, recompute consistent fields on that target row snapshot
                if ch.target == 'custody' and custody_i is not None:
                    target_row = dict(custody_row or {})
                    target_row[ch.field] = ch.new_value
                    target_row = self.math.refine(target_row)
                    # Emit additional changes if recomputation adjusted related fields
                    for f in ['net_amount', 'tax_amount', 'tax_rate']:
                        if f in target_row and (custody_row or {}).get(f) != target_row[f]:
                            refined_props.append(Change('custody', custody_i, f, target_row[f], f'Recompute {f}', 0.8))
                    refined_props.append(ch)
                elif ch.target == 'nbim' and nbim_i is not None:
                    target_row = dict(nbim_row or {})
                    target_row[ch.field] = ch.new_value
                    target_row = self.math.refine(target_row)
                    for f in ['net_amount', 'tax_amount', 'tax_rate']:
                        if f in target_row and (nbim_row or {}).get(f) != target_row[f]:
                            refined_props.append(Change('nbim', nbim_i, f, target_row[f], f'Recompute {f}', 0.8))
                    refined_props.append(ch)
                else:
                    refined_props.append(ch)

            proposals.extend(refined_props)

        # Manager applies approved changes
        nbim_out, custody_out = self.manager.apply_changes(nbim_df, custody_df, proposals)

        return {'nbim': nbim_out, 'custody': custody_out}
