#!/usr/bin/env python3
"""
IC (Information Coefficient) Test for ePDF Signal Quality

Question: Does the ePDF probability distribution actually predict future range?

Method:
  For each tau-bar j (after warmup):
    - Signal: E[RangeUp|state_j] or E[RangeDown|state_j] from walk-forward ePDF
    - Realized: actual RangeUp / RangeDown in ticks
    - IC = Spearman rank correlation (signal vs realized)
    - Also test unconditional ePDF vs conditional ePDF
    - Also test naive baseline (historical mean)

  This strips away ALL execution rules. Pure signal quality test.

Usage:
  python ic_test_epdf.py
  python ic_test_epdf.py --asset Gold
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from scipy import stats

# ── Config ──
ASSETS_DIR = Path("strategy_all")
TAU = 45
WARMUP = 60
MAX_SPREAD = 80
EWMA_HALF_LIFE = 25
TARGET_MEDIAN_ELL = 45

TICK_MAP = {
    "EuroStoxx": 0.5,
    "GBP - British Pound": 0.01,
    "German Bunds - German Government Bonds": 0.01,
    "Gold": 0.1,
    "Heating_oil": 0.01,
    "JPY - Japanese Yen": 0.005,
    "Nasdaq": 0.25,
}

ASSETS = list(TICK_MAP.keys())

# ── ePDF class (minimal, no execution logic) ──
class SimpleEPDF:
    """Walk-forward empirical distribution, no execution rules."""

    def __init__(self, max_spread: int = MAX_SPREAD):
        self.max_spread = max_spread
        self.counts_uncond = {"R": {}, "RU": {}, "RD": {}}
        self.counts_cond = {"R": {}, "RU": {}, "RD": {}}

    def update(self, ell: int, ell_u: int, ell_d: int, state: Tuple):
        mapping = {"R": ell, "RU": ell_u, "RD": ell_d}
        for kind, val in mapping.items():
            val = int(np.clip(val, 0, self.max_spread))
            self.counts_uncond[kind][val] = self.counts_uncond[kind].get(val, 0) + 1
            self.counts_cond[kind].setdefault(state, {})
            self.counts_cond[kind][state][val] = self.counts_cond[kind][state].get(val, 0) + 1

    def expected_value(self, kind: str, state: Optional[Tuple] = None,
                       max_d: int = 80, smooth: float = 1.0) -> float:
        """E[d] under conditional or unconditional distribution."""
        if state is not None:
            c = self.counts_cond.get(kind, {}).get(state, {})
            if c:
                total = sum(c.values()) + smooth * (max_d + 1)
                ev = sum((d * (c.get(d, 0) + smooth)) for d in range(max_d + 1)) / total
                return ev
        # Fallback to unconditional
        c = self.counts_uncond.get(kind, {})
        if not c:
            return 0.0
        total = sum(c.values()) + smooth * (max_d + 1)
        return sum((d * (c.get(d, 0) + smooth)) for d in range(max_d + 1)) / total

    def prob_ge(self, kind: str, state: Optional[Tuple], d: int, smooth: float = 1.0) -> float:
        """P(range >= d | state)"""
        if state is not None:
            c = self.counts_cond.get(kind, {}).get(state, {})
            if c:
                total = sum(c.values()) + smooth * (self.max_spread + 1)
                tail = sum((c.get(k, 0) + smooth) for k in range(d, self.max_spread + 1))
                return tail / total
        c = self.counts_uncond.get(kind, {})
        if not c:
            return 0.5
        total = sum(c.values()) + smooth * (self.max_spread + 1)
        return sum((c.get(k, 0) + smooth) for k in range(d, self.max_spread + 1)) / total

    def entropy(self, kind: str, state: Optional[Tuple], max_d: int = 40,
                smooth: float = 1.0) -> float:
        """Shannon entropy of the distribution (bits)."""
        if state is not None:
            c = self.counts_cond.get(kind, {}).get(state, {})
            if c:
                total = sum(c.values()) + smooth * (max_d + 1)
                probs = [(c.get(d, 0) + smooth) / total for d in range(max_d + 1)]
                return -sum(p * np.log2(p) for p in probs if p > 0)
        c = self.counts_uncond.get(kind, {})
        if not c:
            return 0.0
        total = sum(c.values()) + smooth * (max_d + 1)
        probs = [(c.get(d, 0) + smooth) / total for d in range(max_d + 1)]
        return -sum(p * np.log2(p) for p in probs if p > 0)


# ── Feature building (same as order_execution_project.py) ──
def ewma_series(series: np.ndarray, half_life: int) -> Tuple[np.ndarray, np.ndarray]:
    n = len(series)
    lam = 2 ** (-1.0 / half_life)
    ewma = np.full(n, np.nan)
    ewmv = np.full(n, np.nan)
    sum_w = 0.0
    sum_wx = 0.0
    sum_wss = 0.0
    for j in range(n):
        eta = series[j]
        if np.isnan(eta):
            if j > 0:
                ewma[j] = ewma[j - 1]
                ewmv[j] = ewmv[j - 1]
            continue
        if sum_w == 0:
            sum_w = 1.0
            sum_wx = eta
            ewma[j] = eta
        else:
            sum_w = lam * sum_w + 1.0
            sum_wx = lam * sum_wx + eta
            ewma[j] = sum_wx / sum_w
            sum_wss = lam * sum_wss + (eta - ewma[j]) ** 2
            ewmv[j] = np.sqrt(sum_wss / sum_w) if sum_w > 0 else 0.0
    return ewma, ewmv


def assign_tertile_bins(series: np.ndarray, j: int) -> int:
    hist = series[:j]
    hist = hist[np.isfinite(hist)]
    if len(hist) < 30:
        return 1
    q1, q2 = np.quantile(hist, [1 / 3, 2 / 3])
    val = series[j - 1]
    if val <= q1:
        return 0
    if val <= q2:
        return 1
    return 2


def calibrate_ell_divisor(bars: pd.DataFrame, tick: float) -> float:
    tmp_ell = ((bars["high"] - bars["low"]) / tick).values
    med = np.nanmedian(tmp_ell[np.isfinite(tmp_ell)])
    if med > 0:
        return max(1.0, med / TARGET_MEDIAN_ELL)
    return 1.0


def build_features(bars: pd.DataFrame, tick: float, ell_divisor: float = 1.0) -> pd.DataFrame:
    div = max(1.0, float(ell_divisor))
    feat = bars.copy()
    feat["ell"] = ((bars["high"] - bars["low"]) / tick / div).round().astype(int).clip(0, MAX_SPREAD)
    feat["ell_u"] = ((bars["high"] - bars["open"]) / tick / div).round().astype(int).clip(0, MAX_SPREAD)
    feat["ell_d"] = ((bars["open"] - bars["low"]) / tick / div).round().astype(int).clip(0, MAX_SPREAD)

    ell = feat["ell"].to_numpy(dtype=float)
    vol = feat["volume"].to_numpy(dtype=float) if "volume" in feat.columns else np.ones(len(feat))
    ewma_ell, ewmv_ell = ewma_series(ell, EWMA_HALF_LIFE)
    ewma_vol, _ = ewma_series(vol, EWMA_HALF_LIFE)
    close = feat["close"].to_numpy()
    delta_x = np.zeros(len(feat))
    delta_x[1:] = close[1:] - close[:-1]

    vol_bin = np.zeros(len(feat), dtype=int)
    sig_bin = np.zeros(len(feat), dtype=int)
    trend_bin = np.ones(len(feat), dtype=int)
    for j in range(1, len(feat)):
        vol_bin[j] = assign_tertile_bins(ewma_vol, j)
        sig_bin[j] = assign_tertile_bins(ewmv_ell, j)
        dx = delta_x[j - 1]
        if dx > tick:
            trend_bin[j] = 2
        elif dx < -tick:
            trend_bin[j] = 0
        else:
            trend_bin[j] = 1

    feat["ewma_range"] = ewma_ell
    feat["ewmv_range"] = ewmv_ell
    feat["vol_bin"] = vol_bin
    feat["sig_bin"] = sig_bin
    feat["trend_bin"] = trend_bin
    feat["state"] = list(zip(vol_bin, sig_bin, trend_bin))
    return feat


# ── IC Computation ──
def compute_ic_for_asset(asset: str) -> pd.DataFrame:
    """Walk-forward IC test: does ePDF predict realized range?"""
    tick = TICK_MAP[asset]
    feat_path = ASSETS_DIR / asset / "features_tau45.csv"
    stitched_path = ASSETS_DIR / asset / "stitched_1min.csv"

    if not feat_path.exists() or not stitched_path.exists():
        print(f"  {asset}: missing data, skipping")
        return pd.DataFrame()

    feat = pd.read_csv(feat_path, index_col=0, parse_dates=True)

    # Build walk-forward ePDF and record predictions
    epdf = SimpleEPDF()
    records = []

    for j in range(WARMUP, len(feat)):
        # Update ePDF with bar j-1 (completed before signal)
        epdf.update(
            int(feat["ell"].iloc[j - 1]),
            int(feat["ell_u"].iloc[j - 1]),
            int(feat["ell_d"].iloc[j - 1]),
            feat["state"].iloc[j - 1] if isinstance(feat["state"].iloc[j - 1], tuple) else
            (int(feat["vol_bin"].iloc[j - 1]), int(feat["sig_bin"].iloc[j - 1]), int(feat["trend_bin"].iloc[j - 1])),
        )

        # Current state
        st = feat["state"].iloc[j]
        if not isinstance(st, tuple):
            st = (int(feat["vol_bin"].iloc[j]), int(feat["sig_bin"].iloc[j]), int(feat["trend_bin"].iloc[j]))

        # Realized values for bar j
        realized_ru = int(feat["ell_u"].iloc[j])
        realized_rd = int(feat["ell_d"].iloc[j])
        realized_r = int(feat["ell"].iloc[j])

        # Predictions: E[range | state]
        ev_ru_cond = epdf.expected_value("RU", state=st)
        ev_rd_cond = epdf.expected_value("RD", state=st)
        ev_r_cond = epdf.expected_value("R", state=st)

        # Predictions: E[range] unconditional
        ev_ru_uncond = epdf.expected_value("RU", state=None)
        ev_rd_uncond = epdf.expected_value("RD", state=None)
        ev_r_uncond = epdf.expected_value("R", state=None)

        # Naive baseline: EWMA of range (the ewma_range feature itself)
        ewma_r = feat["ewma_range"].iloc[j]
        ewmv_r = feat["ewmv_range"].iloc[j]

        # Entropy (information content)
        ent_cond = epdf.entropy("R", state=st)
        ent_uncond = epdf.entropy("R", state=None)

        # Tail probabilities at key levels
        p_ru_ge10 = epdf.prob_ge("RU", state=st, d=10)
        p_rd_ge10 = epdf.prob_ge("RD", state=st, d=10)
        p_r_ge30 = epdf.prob_ge("R", state=st, d=30)

        records.append({
            "bar_idx": j,
            "datetime": feat.index[j],
            "asset": asset,
            "state": st,
            "vol_bin": st[0],
            "sig_bin": st[1],
            "trend_bin": st[2],
            "realized_R": realized_r,
            "realized_RU": realized_ru,
            "realized_RD": realized_rd,
            "pred_E_R_cond": ev_r_cond,
            "pred_E_RU_cond": ev_ru_cond,
            "pred_E_RD_cond": ev_rd_cond,
            "pred_E_R_uncond": ev_r_uncond,
            "pred_E_RU_uncond": ev_ru_uncond,
            "pred_E_RD_uncond": ev_rd_uncond,
            "pred_ewma_R": ewma_r,
            "pred_ewmv_R": ewmv_r,
            "entropy_cond": ent_cond,
            "entropy_uncond": ent_uncond,
            "p_ru_ge10": p_ru_ge10,
            "p_rd_ge10": p_rd_ge10,
            "p_r_ge30": p_r_ge30,
        })

    return pd.DataFrame(records)


def analyze_ic(df: pd.DataFrame, asset: str) -> Dict:
    """Compute IC metrics for one asset."""
    results = {}

    # 1. Main IC: Spearman correlation between predicted and realized
    for target, kind in [("R", "Total Range"), ("RU", "RangeUp"), ("RD", "RangeDown")]:
        realized = df[f"realized_{target}"]
        for pred_col, label in [
            (f"pred_E_{target}_cond", "ePDF conditional"),
            (f"pred_E_{target}_uncond", "ePDF unconditional"),
            ("pred_ewma_R", "EWMA range"),
        ]:
            pred = df[pred_col]
            mask = np.isfinite(pred) & np.isfinite(realized)
            if mask.sum() < 30:
                continue
            ic, pval = stats.spearmanr(pred[mask], realized[mask])
            pearson_ic, _ = stats.pearsonr(pred[mask], realized[mask])
            results[f"{target}_{label}"] = {
                "spearman_ic": ic,
                "pearson_ic": pearson_ic,
                "p_value": pval,
                "n_obs": mask.sum(),
            }

    # 2. Conditional IC by state components
    for dim_name, dim_col in [("vol_bin", "vol_bin"), ("sig_bin", "sig_bin"), ("trend_bin", "trend_bin")]:
        for val in sorted(df[dim_col].unique()):
            sub = df[df[dim_col] == val]
            if len(sub) < 30:
                continue
            realized = sub["realized_R"]
            pred = sub["pred_E_R_cond"]
            mask = np.isfinite(pred) & np.isfinite(realized)
            if mask.sum() < 30:
                continue
            ic, pval = stats.spearmanr(pred[mask], realized[mask])
            results[f"R_cond_by_{dim_name}_{val}"] = {
                "spearman_ic": ic,
                "p_value": pval,
                "n_obs": mask.sum(),
                "subgroup": f"{dim_name}={val}",
            }

    # 3. Conditional vs Unconditional: does state help?
    # IC improvement from conditioning
    ic_cond = results.get("R_ePDF conditional", {}).get("spearman_ic", 0)
    ic_uncond = results.get("R_ePDF unconditional", {}).get("spearman_ic", 0)
    ic_ewma = results.get("R_EWMA range", {}).get("spearman_ic", 0)

    results["summary"] = {
        "ic_conditional": ic_cond,
        "ic_unconditional": ic_uncond,
        "ic_ewma": ic_ewma,
        "state_value_added": ic_cond - ic_uncond,
        "cond_vs_ewma": ic_cond - ic_ewma,
    }

    # 4. Tail prediction accuracy
    # Hit rate: P(R>=30) > 0.5 → did R actually >= 30?
    for threshold in [10, 20, 30, 50]:
        pred_col = f"p_r_ge{threshold}" if threshold != 10 else "p_ru_ge10"
        if pred_col not in df.columns:
            continue
        realized_binary = (df["realized_R"] >= threshold).astype(int)
        pred_prob = df[pred_col]
        # Brier score
        brier = np.mean((pred_prob - realized_binary) ** 2)
        # AUROC
        try:
            from sklearn.metrics import roc_auc_score
            auroc = roc_auc_score(realized_binary, pred_prob)
        except (ImportError, ValueError):
            auroc = np.nan
        results[f"tail_R_ge{threshold}"] = {
            "brier_score": brier,
            "auroc": auroc,
            "actual_freq": realized_binary.mean(),
            "mean_pred_prob": pred_prob.mean(),
        }

    # 5. Entropy analysis: information content by state
    ent_by_state = df.groupby("sig_bin")["entropy_cond"].mean()
    results["entropy_by_vol_regime"] = ent_by_state.to_dict()

    return results


def print_ic_report(all_results: Dict):
    """Print comprehensive IC report."""
    print("\n" + "=" * 90)
    print("IC TEST: Does ePDF Actually Predict Future Range?")
    print("=" * 90)

    # Summary table
    print(f"\n{'Asset':<35s} {'IC(cond)':>10s} {'IC(uncond)':>10s} {'IC(EWMA)':>10s} {'State +':>10s} {'vs EWMA':>10s}")
    print("-" * 90)
    for asset in sorted(all_results.keys()):
        r = all_results[asset].get("summary", {})
        if not r:
            continue
        ic_c = r.get("ic_conditional", np.nan)
        ic_u = r.get("ic_unconditional", np.nan)
        ic_e = r.get("ic_ewma", np.nan)
        sv = r.get("state_value_added", np.nan)
        cv = r.get("cond_vs_ewma", np.nan)
        print(f"{asset:<35s} {ic_c:>10.4f} {ic_u:>10.4f} {ic_e:>10.4f} {sv:>10.4f} {cv:>10.4f}")

    # Interpretation
    print("\n" + "=" * 90)
    print("INTERPRETATION")
    print("=" * 90)
    print("IC (Spearman) > 0.05: meaningful signal")
    print("IC > 0.10: strong signal")
    print("IC > 0.20: very strong signal")
    print("State value added = IC(cond) - IC(uncond): does state conditioning help?")
    print("vs EWMA = IC(cond) - IC(EWMA): does ePDF beat simple moving average?")

    # Per-asset detail
    for asset in sorted(all_results.keys()):
        r = all_results[asset]
        if not r:
            continue
        print(f"\n{'─' * 70}")
        print(f"{asset}")
        print(f"{'─' * 70}")

        # Main IC results
        for key in ["R_ePDF conditional", "R_ePDF unconditional", "R_EWMA range"]:
            if key in r:
                d = r[key]
                sig = "***" if d["p_value"] < 0.001 else "**" if d["p_value"] < 0.01 else "*" if d["p_value"] < 0.05 else ""
                print(f"  {key:30s}: IC={d['spearman_ic']:.4f} (Pearson={d['pearson_ic']:.4f}) p={d['p_value']:.2e} {sig}")

        # Direction-specific IC
        for direction in ["RangeUp", "RangeDown"]:
            key = f"{direction[2]}_ePDF conditional"
            if key in r:
                d = r[key]
                print(f"  {direction:30s}: IC={d['spearman_ic']:.4f} p={d['p_value']:.2e}")

        # State breakdown
        print(f"  IC by state component:")
        for key, val in r.items():
            if key.startswith("R_cond_by_"):
                sg = val.get("subgroup", "")
                print(f"    {sg:20s}: IC={val['spearman_ic']:.4f} n={val['n_obs']} p={val['p_value']:.2e}")

        # Tail prediction
        for key, val in r.items():
            if key.startswith("tail_"):
                print(f"  {key}: Brier={val['brier_score']:.4f}, AUROC={val.get('auroc', np.nan):.4f}, "
                      f"actual_freq={val['actual_freq']:.3f}, pred_freq={val['mean_pred_prob']:.3f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", type=str, default=None)
    args = parser.parse_args()

    assets = [args.asset] if args.asset else ASSETS
    output_dir = Path("attribution_outputs")
    output_dir.mkdir(exist_ok=True)

    all_results = {}

    for asset in assets:
        print(f"\nProcessing {asset}...")
        try:
            df = compute_ic_for_asset(asset)
            if df.empty:
                continue
            print(f"  {len(df):,} bars after warmup")

            results = analyze_ic(df, asset)
            all_results[asset] = results

            # Save per-asset predictions
            df.to_csv(output_dir / f"ic_predictions_{asset.replace(' ', '_').replace('-', '')}.csv", index=False)

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    if all_results:
        print_ic_report(all_results)

        # Save summary
        summary_rows = []
        for asset, r in all_results.items():
            s = r.get("summary", {})
            row = {"asset": asset}
            row.update(s)
            # Add main IC values
            for key in ["R_ePDF conditional", "R_ePDF unconditional", "R_EWMA range",
                        "RU_ePDF conditional", "RD_ePDF conditional"]:
                if key in r:
                    short = key.replace(" ", "_").replace("=", "")
                    row[f"ic_{short}"] = r[key]["spearman_ic"]
                    row[f"pval_{short}"] = r[key]["p_value"]
            summary_rows.append(row)

        summary_df = pd.DataFrame(summary_rows)
        summary_df.to_csv(output_dir / "ic_summary.csv", index=False)
        print(f"\nSaved: {output_dir / 'ic_summary.csv'}")


if __name__ == "__main__":
    main()
