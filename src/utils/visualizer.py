"""
Visualizer Module
Required deliverable: ePDF histograms, fill probability charts
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


class Visualizer:
    """Visualization for ePDF and backtest results"""
    
    def __init__(self):
        """Initialize visualizer"""
        plt.style.use('seaborn-v0_8-darkgrid')
    
    def plot_epdf_histogram(
        self,
        epdfs: dict,
        bins: int = 30,
        save_path: str = None
    ):
        """
        Plot ePDF histograms for all states.
        
        Args:
            epdfs: Dictionary {state: array of values}
            bins: Number of histogram bins
            save_path: Path to save plot
        """
        fig, axes = plt.subplots(1, 3, figsize=(15, 4))
        states = ["Low", "Med", "High"]
        
        for idx, state in enumerate(states):
            ax = axes[idx]
            values = epdfs[state]
            
            if len(values) > 0:
                ax.hist(values, bins=bins, edgecolor='black', alpha=0.7)
                ax.axvline(np.median(values), color='red', linestyle='--', label='Median')
                ax.axvline(np.percentile(values, 50), color='blue', linestyle=':', label='P50')
                ax.axvline(np.percentile(values, 80), color='green', linestyle=':', label='P80')
                ax.set_xlabel('Range Downward (ticks)')
                ax.set_ylabel('Frequency')
                ax.set_title(f'ePDF - {state} Volatility State\nn={len(values)} bars')
                ax.legend()
            else:
                ax.set_title(f'ePDF - {state} Volatility\n(No Data)')
        
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def plot_fill_probability(
        self,
        df: pd.DataFrame,
        save_path: str = None
    ):
        """
        Plot fill probability curve (survival-style).
        
        Args:
            df: DataFrame with fill probabilities per distance
            save_path: Path to save plot
        """
        # Calculate fill probability: P(filled | distance)
        # This is a function of how far limit is from open
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Sample calculation: P(fill) = count(when fill) / count(total)
        # We bin by distance ticks and calculate fill rate per bin
        # Note: This requires fill data from backtest
        
        # Placeholder - actual calculation needs backtest results
        # distances = np.arange(0, 20, 0.5)
        # fill_probs = 1 - (1 - 0.3)**distances  # Example decay curve
        
        # ax.plot(distances, fill_probs, linewidth=2)
        # ax.set_xlabel('Distance (ticks from open)')
        # ax.set_ylabel('Fill Probability')
        # ax.set_title('Fill Probability vs. Limit Order Distance')
        
        ax.text(0.5, 0.5, 'Fill Probability Chart\n(Requires backtest data)',
               ha='center', va='center', transform=ax.transAxes)
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.show()
    
    def plot_backtest_comparison(
        self,
        baseline_returns: list,
        strategy_returns: list,
        save_path: str = None
    ):
        """
        Plot cumulative returns comparison.
        
        Args:
            baseline_returns: Returns from baseline (market order)
            : Returns from strategy
            save_path: Path to save
        """
        fig, ax = plt.subplots(figsize=(10, 6))
        
        cum_baseline = np.cumsum(baseline_returns)
        cum_strategy = np.cumsum(strategy_returns)
        
        ax.plot(cum_baseline, label='Baseline (Market Order)', alpha=0.7)
        ax.plot(cum_strategy, label='Strategy', alpha=0.7)
        ax.axhline(0, color='gray', linestyle='--', linewidth=0.5)
        ax.set_xlabel('Trade')
        ax.set_ylabel('Cumulative Savings (ticks)')
        ax.set_title('Backtest: Strategy vs. Baseline')
        ax.legend()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
    
    def plot_state_distribution(self, df: pd.DataFrame, save_path: str = None):
        """
        Plot distribution of states.
        """
        fig, ax = plt.subplots(figsize=(8, 6))
        
        state_counts = df['vol_state'].value_counts()
        state_counts.plot(kind='bar', color=['green', 'yellow', 'red'])
        ax.set_xlabel('Volatility State')
        ax.set_ylabel('Count')
        ax.set_title('Distribution of Volatility States')
        ax.set_xticklabels(['Low', 'Med', 'High'])
        
        for i, count in enumerate(state_counts):
            ax.text(i, count + 10, str(count), ha='center')
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()