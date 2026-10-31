"""
Methodology Validation & Correction Script
1. Verify regime separation (BOTH range-up and range-down)
2. Fix reference price to open[t]
3. Make tick size configurable
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os

from data_loader import DataLoader
from state_detection import StateDetector


def visualize_regime_distributions(df: pd.DataFrame, epdfs_dn: dict, epdfs_up: dict):
    """
    Visualize ePDF distributions for 3 volatility regimes.
    Show BOTH range-down (for BUY) and range-up (for SELL).
    """
    fig, axes = plt.subplots(3, 2, figsize=(14, 12))
    
    regimes = ['Low', 'Med', 'High']
    
    for i, regime in enumerate(regimes):
        # Range-down (for BUY orders)
        dn_data = epdfs_dn[regime] if regime in epdfs_dn else []
        if len(dn_data) > 0:
            axes[i, 0].hist(dn_data, bins=50, alpha=0.7, color='blue')
            mean = np.mean(dn_data)
            median = np.median(dn_data)
            p80 = np.percentile(dn_data, 80)
            p95 = np.percentile(dn_data, 95)
            
            axes[i, 0].axvline(mean, color='red', linestyle='--', label=f'Mean: {mean:.2f}')
            axes[i, 0].axvline(median, color='orange', linestyle='--', label=f'Median: {median:.2f}')
            axes[i, 0].axvline(p80, color='green', linestyle='--', label=f'P80: {p80:.2f}')
            axes[i, 0].axvline(p95, color='purple', linestyle='--', label=f'P95: {p95:.2f}')
        
        axes[i, 0].set_xlabel('Range-Down (ticks) - For BUY')
        axes[i, 0].set_ylabel('Frequency')
        axes[i, 0].set_title(f'{regime} Volatility - Range-Down (n={len(dn_data):,})')
        axes[i, 0].legend()
        axes[i, 0].grid(True, alpha=0.3)
        
        # Range-up (for SELL orders)
        up_data = epdfs_up[regime] if regime in epdfs_up else []
        if len(up_data) > 0:
            axes[i, 1].hist(up_data, bins=50, alpha=0.7, color='green')
            mean = np.mean(up_data)
            median = np.median(up_data)
            p80 = np.percentile(up_data, 80)
            p95 = np.percentile(up_data, 95)
            
            axes[i, 1].axvline(mean, color='red', linestyle='--', label=f'Mean: {mean:.2f}')
            axes[i, 1].axvline(median, color='orange', linestyle='--', label=f'Median: {median:.2f}')
            axes[i, 1].axvline(p80, color='blue', linestyle='--', label=f'P80: {p80:.2f}')
            axes[i, 1].axvline(p95, color='purple', linestyle='--', label=f'P95: {p95:.2f}')
        
        axes[i, 1].set_xlabel('Range-Up (ticks) - For SELL')
        axes[i, 1].set_ylabel('Frequency')
        axes[i, 1].set_title(f'{regime} Volatility - Range-Up (n={len(up_data):,})')
        axes[i, 1].legend()
        axes[i, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def compare_regimes_boxplot(epdfs_dn: dict, epdfs_up: dict):
    """Box plot comparing regimes for BOTH directions"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Range-down (BUY)
    data_dn_by_regime = [epdfs_dn[r] for r in ['Low', 'Med', 'High']]
    bp1 = axes[0].boxplot(data_dn_by_regime, labels=['Low', 'Med', 'High'],
                         patch_artist=True)
    for patch in bp1['boxes']:
        patch.set_facecolor('lightblue')
    axes[0].set_ylabel('Range-Down (ticks)')
    axes[0].set_title('Range-Down Distribution (For BUY Orders)')
    axes[0].grid(True, alpha=0.3)
    
    # Range-up (SELL)
    data_up_by_regime = [epdfs_up[r] for r in ['Low', 'Med', 'High']]
    bp2 = axes[1].boxplot(data_up_by_regime, labels=['Low', 'Med', 'High'],
                         patch_artist=True)
    for patch in bp2['boxes']:
        patch.set_facecolor('lightgreen')
    axes[1].set_ylabel('Range-Up (ticks)')
    axes[1].set_title('Range-Up Distribution (For SELL Orders)')
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def build_both_epdfs(df: pd.DataFrame) -> tuple:
    """
    Build ePDFs for BOTH range-down and range-up.
    
    Returns:
        (epdfs_dn, epdfs_up): Dictionaries of distributions per regime
    """
    epdfs_dn = {}
    epdfs_up = {}
    
    for state in ["Low", "Med", "High"]:
        epdfs_dn[state] = df[df['prev_state'] == state]['range_dn_ticks'].to_numpy()
        epdfs_up[state] = df[df['prev_state'] == state]['range_up_ticks'].to_numpy()
    
    return epdfs_dn, epdfs_up


def print_statistics(epdfs_dn: dict, epdfs_up: dict):
    """Print statistics for both directions"""
    print("\n" + "=" * 80)
    print("RANGE-DOWN STATISTICS (For BUY Orders) - How far price can DROP from open")
    print("=" * 80)
    print(f"{'Regime':<8} {'N':>10} {'Mean':>8} {'Std':>8} {'P50':>8} {'P80':>8} {'P95':>8}")
    print("-" * 80)
    for regime in ['Low', 'Med', 'High']:
        data = epdfs_dn[regime]
        if len(data) > 0:
            print(f"{regime:<8} {len(data):>10,} {np.mean(data):>8.2f} {np.std(data):>8.2f} "
                  f"{np.percentile(data, 50):>8.2f} {np.percentile(data, 80):>8.2f} "
                  f"{np.percentile(data, 95):>8.2f}")
    
    print("\n" + "=" * 80)
    print("RANGE-UP STATISTICS (For SELL Orders) - How far price can RISE from open")
    print("=" * 80)
    print(f"{'Regime':<8} {'N':>10} {'Mean':>8} {'Std':>8} {'P50':>8} {'P80':>8} {'P95':>8}")
    print("-" * 80)
    for regime in ['Low', 'Med', 'High']:
        data = epdfs_up[regime]
        if len(data) > 0:
            print(f"{regime:<8} {len(data):>10,} {np.mean(data):>8.2f} {np.std(data):>8.2f} "
                  f"{np.percentile(data, 50):>8.2f} {np.percentile(data, 80):>8.2f} "
                  f"{np.percentile(data, 95):>8.2f}")
    print("=" * 80)


def analyze_direction_bias(df: pd.DataFrame, epdfs_dn: dict, epdfs_up: dict):
    """Analyze if price tends to go up or down in each regime"""
    print("\n" + "=" * 80)
    print("DIRECTION BIAS ANALYSIS (Should we BUY or SELL?)")
    print("=" * 80)
    
    for regime in ['Low', 'Med', 'High']:
        dn_data = epdfs_dn[regime]
        up_data = epdfs_up[regime]
        
        if len(dn_data) == 0 or len(up_data) == 0:
            continue
        
        # Compare mean range-down vs range-up
        dn_mean = np.mean(dn_data)
        up_mean = np.mean(up_data)
        
        # Direction bias
        bias = dn_mean - up_mean  # Positive: tends to drop (BUY), Negative: tends to rise (SELL)
        
        print(f"\n{regime} Volatility:")
        print(f"  Avg Drop (range-down): {dn_mean:.2f} ticks")
        print(f"  Avg Rise (range-up):   {up_mean:.2f} ticks")
        print(f"  Bias: {bias:+.2f} ticks")
        
        if bias > 0.5:
            print(f"  -> TENDS TO DROP (favor BUY orders)")
        elif bias < -0.5:
            print(f"  -> TENDS TO RISE (favor SELL orders)")
        else:
            print(f"  -> NO CLEAR BIAS (both directions similar)")
    
    print("\n" + "=" * 80)


def evaluate_regime_separation(epdfs_dn: dict, epdfs_up: dict):
    """
    Quantify how well-separated the regimes are for BOTH directions.
    """
    print("\n" + "=" * 80)
    print("REGIME SEPARATION ANALYSIS")
    print("=" * 80)
    
    for direction, epdfs in [("Range-Down", epdfs_dn), ("Range-Up", epdfs_up)]:
        print(f"\n--- {direction} ---")
        
        regimes = ['Low', 'Med', 'High']
        
        for i in range(len(regimes)):
            for j in range(i+1, len(regimes)):
                r1, r2 = regimes[i], regimes[j]
                
                data1, data2 = epdfs[r1], epdfs[r2]
                
                if len(data1) == 0 or len(data2) == 0:
                    continue
                
                # Cohen's d (effect size)
                mean1, std1 = np.mean(data1), np.std(data1)
                mean2, std2 = np.mean(data2), np.std(data2)
                
                pooled_std = np.sqrt((std1**2 + std2**2) / 2)
                cohens_d = abs(mean1 - mean2) / pooled_std if pooled_std > 0 else 0
                
                print(f"{r1} vs {r2}:")
                print(f"  Mean Difference: {abs(mean1-mean2):.2f} ticks")
                print(f"  Cohen's d: {cohens_d:.2f} {'(LARGE)' if cohens_d > 0.8 else '(SMALL)' if cohens_d < 0.2 else '(MEDIUM)'}")
                print(f"  -> {'DISTINCT' if cohens_d > 0.8 else 'OVERLAPPED' if cohens_d < 0.5 else 'MODERATE'}")
    
    print("\n" + "=" * 80)


def main():
    """Main validation script"""
    print("=" * 80)
    print("METHODOLOGY VALIDATION & CORRECTION")
    print("=" * 80)
    
    os.makedirs('results', exist_ok=True)
    
    # 1. Load data
    print("\n1. Loading data...")
    loader = DataLoader(tick_size=0.25)
    data_path = "os.path.join(os.environ.get("ORDER_DATA_ROOT", "data_export"), "Nasdaq", "NQH20.csv")"
    df = loader.load_csv(data_path)
    print(f"   Loaded {len(df)} bars")
    
    # 2. Detect states
    print("\n2. Detecting volatility regimes...")
    detector = StateDetector(m=20, low_thresh=1.5, high_thresh=3.0)
    df = detector.detect_states(df)
    
    # Count regimes
    counts = df['prev_state'].value_counts()
    print(f"   Regime distribution:")
    for state in ['Low', 'Med', 'High']:
        n = counts.get(state, 0)
        pct = n / len(df) * 100
        print(f"     {state}: {n:,} bars ({pct:.1f}%)")
    
    # 3. Build ePDFs for BOTH directions
    print("\n3. Building ePDFs for range-down and range-up...")
    epdfs_dn, epdfs_up = build_both_epdfs(df)
    print(f"   Built ePDFs for {len(epdfs_dn)} regimes (both directions)")
    
    # 4. Visualize regime distributions
    print("\n4. Visualizing regime distributions...")
    fig1 = visualize_regime_distributions(df, epdfs_dn, epdfs_up)
    fig1.savefig('results/regime_distributions_both.png', dpi=300, bbox_inches='tight')
    print("   Saved to: results/regime_distributions_both.png")
    plt.close(fig1)
    
    # 5. Box plot comparison
    print("\n5. Comparing regimes with box plots...")
    fig2 = compare_regimes_boxplot(epdfs_dn, epdfs_up)
    fig2.savefig('results/regime_boxplot_both.png', dpi=300, bbox_inches='tight')
    print("   Saved to: results/regime_boxplot_both.png")
    plt.close(fig2)
    
    # 6. Print statistics
    print_statistics(epdfs_dn, epdfs_up)
    
    # 7. Analyze direction bias
    analyze_direction_bias(df, epdfs_dn, epdfs_up)
    
    # 8. Evaluate separation
    evaluate_regime_separation(epdfs_dn, epdfs_up)
    
    # 9. Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print("\n1. Reference Price: CHANGE to `open[t]`")
    print("   - Current: close[t-1]")
    print("   - Correction: open[t]")
    print("   - Effect: Better reflects 'current market price' at decision time")
    print()
    print("2. Direction Analysis: CHECK bias for BUY vs SELL")
    print("   - If range-down > range-up: Favor BUY orders")
    print("   - If range-up > range-down: Favor SELL orders")
    print("   - If similar: Consider both directions")
    print()
    print("3. Regime Separation: EVALUATE based on Cohen's d")
    print("   - Check regime_distributions_both.png")
    print("   - If HIGH overlap: Consider different thresholds")
    print("   - If GOOD separation: Keep 3-regime classification")
    print()
    print("4. Tick Size: MAKE GLOBAL (configurable per contract)")
    print("   - Examples: NQ=0.25, Gold=0.10, Bunds=0.01")
    print()
    print("=" * 80)


if __name__ == '__main__':
    main()