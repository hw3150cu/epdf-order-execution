"""
Multi-Source Data Tester

Tests stochastic control modules across multiple data sources:
- data_export (Nasdaq, Gold, JPY, etc.)
- DataBento (NQ, etc.)

Usage:
    tester = MultiSourceTester()
    results = tester.run_all_tests()
"""

import numpy as np
import pandas as pd
import os
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import warnings

from inventory_tracker import InventoryTracker
from state_transition import StateTransitionEstimator
from dynamic_penalty import DynamicPenalty


class MultiSourceTester:
    """
    Test stochastic control modules across multiple data sources.
    """
    
    def __init__(self, base_path: str = '.'):
        """
        Initialize MultiSourceTester.
        
        Args:
            base_path: Base directory containing data folders
        """
        self.base_path = Path(base_path)
        self.data_export_path = self.base_path / 'data_export'
        self.databento_path = self.base_path / 'DataBento'
        self.results = {}
        
    def _load_data_export(self, folder: str) -> Optional[pd.DataFrame]:
        """Load data from data_export folder."""
        folder_path = self.data_export_path / folder
        
        if not folder_path.exists():
            return None
            
        # Find CSV files
        csv_files = list(folder_path.glob('*.csv'))
        
        if not csv_files:
            return None
            
        # Load first CSV
        try:
            df = pd.read_csv(csv_files[0])
            return df
        except Exception as e:
            print(f"  Error loading {folder}: {e}")
            return None
            
    def _load_databento(self, folder: str) -> Optional[pd.DataFrame]:
        """Load data from DataBento folder."""
        folder_path = self.databento_path / folder
        
        if not folder_path.exists():
            return None
            
        # Find CSV files
        csv_files = list(folder_path.glob('*.csv'))
        
        if not csv_files:
            return None
            
        # Load first CSV
        try:
            df = pd.read_csv(csv_files[0])
            return df
        except Exception as e:
            print(f"  Error loading {folder}: {e}")
            return None
            
    def _find_price_column(self, df: pd.DataFrame) -> Optional[str]:
        """Find price column in DataFrame."""
        price_cols = ['close', 'Close', 'price', 'Price', 'last', 'Last']
        for col in price_cols:
            if col in df.columns:
                return col
        # Try numeric columns
        for col in df.columns:
            if df[col].dtype in [np.float64, np.int64]:
                return col
        return None
        
    def _test_single_source(
        self,
        df: pd.DataFrame,
        source_name: str
    ) -> Dict:
        """Run test on a single data source."""
        # Find price column
        price_col = self._find_price_column(df)
        
        if price_col is None:
            return {
                'source': source_name,
                'status': 'error',
                'error': 'No price column found'
            }
            
        # Ensure we have enough data
        if len(df) < 100:
            return {
                'source': source_name,
                'status': 'error',
                'error': f'Insufficient data: {len(df)} rows'
            }
            
        try:
            # Initialize modules
            tracker = InventoryTracker(target_quantity=100)
            penalty = DynamicPenalty(base_penalty=10.0)
            estimator = StateTransitionEstimator(n_states=3)
            
            # Fit state estimator
            returns = df[price_col].pct_change().dropna()
            if len(returns) > 50:
                estimator.fit_from_returns(returns)
                
            # Run simulation
            T = min(len(df), 60)
            ref_price = df[price_col].iloc[0]
            pnls = []
            
            for t in range(T):
                current_price = df[price_col].iloc[t]
                
                # Calculate penalty
                lambda_t = penalty.calculate(
                    t=t, T=T,
                    current_inventory=tracker.inventory,
                    target_inventory=100
                )
                
                # Simple trading logic
                if tracker.inventory < 100:
                    fill_prob = 0.5 * (1 - lambda_t / 50)
                    fill_prob = max(0.1, min(0.9, fill_prob))
                    
                    if np.random.random() < fill_prob:
                        qty = min(5, 100 - tracker.inventory)
                        pnl = tracker.update(
                            filled_quantity=qty,
                            exec_price=current_price,
                            ref_price=ref_price,
                            side='buy'
                        )
                        pnls.append(pnl)
                        
            # Calculate metrics
            stats = tracker.get_stats()
            
            return {
                'source': source_name,
                'status': 'success',
                'n_rows': len(df),
                'price_col': price_col,
                'total_pnl': stats['total_pnl'],
                'n_trades': stats['trade_count'],
                'fill_rate': stats['fill_rate'],
                'avg_pnl_per_trade': stats['avg_pnl_per_trade'],
                'transition_matrix_shape': estimator.transition_matrix.shape if estimator.transition_matrix is not None else None
            }
            
        except Exception as e:
            return {
                'source': source_name,
                'status': 'error',
                'error': str(e)
            }
            
    def test_data_export(self) -> Dict:
        """Test all data_export sources."""
        print("\n=== Testing data_export sources ===")
        
        results = {}
        
        if not self.data_export_path.exists():
            print("  data_export folder not found")
            return results
            
        folders = [f for f in self.data_export_path.iterdir() if f.is_dir()]
        
        for folder in folders:
            print(f"\n  Testing: {folder.name}")
            df = self._load_data_export(folder.name)
            
            if df is not None:
                result = self._test_single_source(df, f"data_export/{folder.name}")
                results[folder.name] = result
                
                if result['status'] == 'success':
                    print(f"    ✓ Rows: {result['n_rows']}, PnL: {result['total_pnl']:.2f}")
                else:
                    print(f"    ✗ Error: {result.get('error', 'Unknown')}")
            else:
                print(f"    ✗ Could not load data")
                
        return results
        
    def test_databento(self) -> Dict:
        """Test all DataBento sources."""
        print("\n=== Testing DataBento sources ===")
        
        results = {}
        
        if not self.databento_path.exists():
            print("  DataBento folder not found")
            return results
            
        folders = [f for f in self.databento_path.iterdir() if f.is_dir()]
        
        for folder in folders:
            print(f"\n  Testing: {folder.name}")
            df = self._load_databento(folder.name)
            
            if df is not None:
                result = self._test_single_source(df, f"DataBento/{folder.name}")
                results[folder.name] = result
                
                if result['status'] == 'success':
                    print(f"    ✓ Rows: {result['n_rows']}, PnL: {result['total_pnl']:.2f}")
                else:
                    print(f"    ✗ Error: {result.get('error', 'Unknown')}")
            else:
                print(f"    ✗ Could not load data")
                
        return results
        
    def run_all_tests(self) -> Dict:
        """Run tests on all data sources."""
        print("=" * 60)
        print("Multi-Source Data Testing")
        print("=" * 60)
        
        np.random.seed(42)
        
        self.results = {
            'data_export': self.test_data_export(),
            'DataBento': self.test_databento()
        }
        
        return self.results
        
    def get_summary(self) -> pd.DataFrame:
        """Get summary of all test results."""
        rows = []
        
        for source_type, sources in self.results.items():
            for name, result in sources.items():
                row = {
                    'source_type': source_type,
                    'source_name': name,
                    'status': result.get('status', 'unknown'),
                    'n_rows': result.get('n_rows', 0),
                    'total_pnl': result.get('total_pnl', 0),
                    'n_trades': result.get('n_trades', 0),
                    'fill_rate': result.get('fill_rate', 0)
                }
                rows.append(row)
                
        return pd.DataFrame(rows)
        
    def generate_report(self) -> str:
        """Generate text report of results."""
        summary = self.get_summary()
        
        report = []
        report.append("=" * 60)
        report.append("Multi-Source Test Report")
        report.append("=" * 60)
        
        # Success rate
        success_count = (summary['status'] == 'success').sum()
        total_count = len(summary)
        report.append(f"\nSuccess Rate: {success_count}/{total_count}")
        
        # By source type
        for source_type in ['data_export', 'DataBento']:
            subset = summary[summary['source_type'] == source_type]
            if len(subset) > 0:
                report.append(f"\n{source_type}:")
                for _, row in subset.iterrows():
                    status = "✓" if row['status'] == 'success' else "✗"
                    report.append(f"  {status} {row['source_name']}: PnL={row['total_pnl']:.2f}")
                    
        # Best performers
        successful = summary[summary['status'] == 'success']
        if len(successful) > 0:
            best = successful.loc[successful['total_pnl'].idxmax()]
            report.append(f"\nBest Performer: {best['source_name']} (PnL={best['total_pnl']:.2f})")
            
        return "\n".join(report)


def quick_test():
    """Quick test with available data."""
    tester = MultiSourceTester()
    results = tester.run_all_tests()
    print("\n" + tester.generate_report())
    return results


if __name__ == '__main__':
    quick_test()