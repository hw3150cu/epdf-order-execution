"""
Methodology Validation & Correction Script
1. Verify regime separation
2. Fix reference price to open[t]
3. Make tick size configurable
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os

from data_loader import DataLoader
from state_detection import StateDetector
from epdf import build_epdfs


def visualize_regime_distributions(epdfs: dict):
    """
    Visualize ePDF distributions for 3 volatility regimes.
    Check if regimes are distinct enough.
    """
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    for i, (regime, data) in enumerate(epdfs.items()):
        if len(data) == 0:
            continue
        
        # Plot histogram
        axes[i].hist(data, bins=50, alpha=0.7, color='steelblue')
        
        # Statistics
        mean = np.mean(data)
        median = np.median(data)
        p80 = np.percentile(data, 80)
        p95 = np.percentile(data, 95)
        
        axes[i].axvline(mean, color='red', linestyle='--', 
                        label=f'Mean: {mean:.2f}')
        axes[i].axvline(median, color='orange', linestyle='--',
                        label=f'Median: {median:.2f}')
        axes[i].axvline(p80, color='green', linestyle='--',
                        label=f'P80: {p80:.2f}')
        axes[i].axvline(p95, color='purple', linestyle='--',
                        label=f'P95: {p95:.2f}')
        
        axes[i].set_xlabel('Range-Down (ticks)')
        axes[i].set_ylabel('Frequency')
        axes[i].set_title(f'{regime} Volatility (n={len(data):,})')
        axes[i].legend()
        axes[i].grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def compare_regimes_boxplot(epdfs: dict):
    """Box plot comparing regimes"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    data_by_regime = [epdfs[r] for r in ['Low', 'Med', 'High']]
    
    bp = ax.boxplot(data_by_regime, labels=['Low', 'Med', 'High'],
                    patch_artist=True)
    
    for patch in bp['boxes']:
        patch.set_facecolor('lightblue')
    
    ax.set_ylabel('Range-Down (ticks)')
    ax.set_title('Regime Distribution Comparison')
    ax.grid(True, alpha=0.3)
    
    # Add statistics table
    stats = []
    for regime in ['Low', 'Med', 'High']:
        data = epdfs[regime]
        if len(data) > 0:
            stats.append({
                'Regime': regime,
                'N': len(data),
                'Mean': np.mean(data),
                'Std': np.std(data),
                'P50': np.percentile(data, 50),
                'P80': np.percentile(data, 80),
                'P95': np.percentile(data, 95)
            })
    
    print("\n" + "=" * 80)
    print("REGIME STATISTICS (Range-Down in ticks)")
    print("=" * 80)
    print(f"{'Regime':<8} {'N':>10} {'Mean':>8} {'Std':>8} {'P50':>8} {'P80':>8} {'P95':>8}")
    print("-" * 80)
    for s in stats:
        print(f"{s['Regime']:<8} {s['N']:>10,} {s['Mean']:>8.2f} {s['Std']:>8.2f} {s['P50']:>8.2f} {s['P80']:>8.2f} {s['P95']:>8.2f}")
    print("=" * 80)
    
    return fig


def evaluate_regime_separation(epdfs: dict):
    """
    Quantify how well-separated the regimes are.
    """
    print("\n" + "=" * 80)
    print("REGIME SEPARATION ANALYSIS")
    print("=" * 80)
    
    regimes = ['Low', 'Med', 'High']
    
    for i in range(len(regimes)):
        for j in range(i+1, len(regimes)):
            r1, r2 = regimes[i], regimes[j]
            
            # Cohen's d (effect size)
            mean1, std1 = np.mean(epdfs[r1]), np.std(epdfs[r1])
            mean2, std2 = np.mean(epdfs[r2]), np.std(epdfs[r2])
            
            pooled_std = np.sqrt((std1**2 + std2**2) / 2)
            cohens_d = abs(mean1 - mean2) / pooled_std if pooled_std > 0 else 0
            
            # Overlap coefficient
            def overlap_coefficient(mu1, sigma1, mu2, sigma2):
                """Compute overlap of two normal distributions"""
                from scipy.stats import norm
                import numpy as np
                # Integration points
                x = np.linspace(min(mu1-3*sigma1, mu2-3*sigma2),
                                max(mu1+3*sigma1, mu2+3*sigma2), 1000)
                p1 = norm.pdf(x, mu1, sigma1)
                p2 = norm.pdf(x, mu2, sigma2)
                overlap = np.trapz(np.minimum(p1, p2), x)
                normalization = min(np.trapz(p1, x), np.trapz(p2, x))
                return overlap / normalization if normalization > 0 else 0
            
            try:
                overlap = overlap_coefficient(mean1, std1, mean2, std2)
            except:
                overlap = 0.0
            
            print(f"{r1} vs {r2}:")
            print(f"  Mean Difference: {abs(mean1-mean2):.2f} ticks")
            print(f"  Cohen's d: {cohens_d:.2f} {'(LARGE)' if cohens_d > 0.8 else '(SMALL)' if cohens_d < 0.2 else '(MEDIUM)'}")
            print(f"  Overlap: {overlap*100:.1f}%")
            print(f"  -> {'DISTINCT' if cohens_d > 0.8 else 'OVERLAPPED' if cohensd < 0.5 else 'MODERATE'}")
            print()
    
    print("=" * 80)


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
    
    # 3. Build ePDFs
    print("\n3. Building ePDFs per regime...")
    epdfs = build_epdfs(df)
    print(f"   Built ePDFs for {len(epdfs)} regimes")
    
    # 4. Visualize regime distributions
    print("\n4. Visualizing regime distributions...")
    fig1 = visualize_regime_distributions(epdfs)
    fig1.savefig('results/regime_distributions.png', dpi=300, bbox_inches='tight')
    print("   Saved to: results/regime_distributions.png")
    plt.close(fig1)
    
    # 5. Box plot comparison
    print("\n5. Comparing regimes with box plots...")
    fig2 = compare_regimes_boxplot(epdfs)
    fig2.savefig('results/regime_boxplot.png', dpi=300, bbox_inches='tight')
    print("   Saved to: results/regime_boxplot.png")
    plt.close(fig2)
    
    # 6. Evaluate separation
    evaluate_regime_separation(epdfs)
    
    # 7. Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print("\n1. Reference Price: CHANGE to `open[t]`")
    print("   - Current: close[t-1]")
    print("   - Correction: open[t]")
    print("   - Effect: Better reflects 'current market price' at decision time")
    print()
    print("2. Regime Separation: EVALUATE based on Cohen's d and overlap")
    print("   - Check boxplot and histograms")
    - If HIGH overlap: Consider different thresholds or 2 regimes")
    print("   - If GOOD separation: Keep 3-regime classification")
    print()
    print("3. Tick Size: MAKE GLOBAL")
    print("   - Current: Hardcoded 0.25")
    print("   - Correction: Configurable per contract")
    print("   - Examples: NQ=0.25, Gold=0.10, Bunds=0.01")
    print()
    print("=" * 80)


if __name__ == '__main__':
    main()