"""
Monte Carlo Bootstrap Module for Backtesting Robustness Validation

This module provides tools to:
1. Detect CSV files with 9-character filenames
2. Load and extract OHLC data from these files
3. Generate bootstrap resamples (synthetic paths)
4. Validate strategy robustness through resampling
"""

import os
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from tqdm import tqdm


def detect_csv_files(base_dir: str) -> List[str]:
    """
    Detect all CSV files with 9-character filenames in data_export/ subdirectories.
    
    Args:
        base_dir: Base directory to search (default: TermProject/data_export)
        
    Returns:
        List of absolute paths to CSV files with 9-char filenames
        
    Example:
        >>> files = detect_csv_files("path/to/data_export")
        >>> print(f"Found {len(files)} files")
    """
    csv_files = []
    
    data_export_dir = os.path.join(base_dir, "data_export")
    
    if not os.path.exists(data_export_dir):
        print(f"Warning: {data_export_dir} does not exist")
        return csv_files
    
    # Walk through all subdirectories
    for root, dirs, files in os.walk(data_export_dir):
        for file in files:
            # Check if filename is exactly 9 characters (e.g., "NQH20.csv")
            if len(file) == 9 and file.endswith('.csv'):
                file_path = os.path.join(root, file)
                csv_files.append(file_path)
    
    print(f"Detected {len(csv_files)} CSV files with 9-character filenames:")
    for file_path in csv_files:
        rel_path = os.path.relpath(file_path, base_dir)
        print(f"  - {rel_path}")
    
    return csv_files


def load_csv_data(csv_path: str) -> pd.DataFrame:
    """
    Load CSV file and extract OHLC columns.
    
    CSV format: date, Open, High, Low, Close, volume (6 columns)
    OHLC columns are indices 1-4 (0-indexed)
    
    Args:
        csv_path: Absolute path to CSV file
        
    Returns:
        DataFrame with columns: [open, high, low, close, volume]
        
    Raises:
        ValueError: If CSV has insufficient columns or invalid format
    """
    try:
        # Read CSV without header
        df = pd.read_csv(csv_path, header=None)
        
        # Check minimum columns required
        if df.shape[1] < 5:
            raise ValueError(f"CSV has only {df.shape[1]} columns, need at least 5")
        
        # Extract OHLC columns (indices 1,2,3,4 for Open, High, Low, Close)
        # Also include volume (column 5 if available)
        ohlc_columns = {
            'open': df.iloc[:, 1],
            'high': df.iloc[:, 2],
            'low': df.iloc[:, 3],
            'close': df.iloc[:, 4]
        }
        
        # Add volume if available
        if df.shape[1] >= 6:
            ohlc_columns['volume'] = df.iloc[:, 5]
        
        result_df = pd.DataFrame(ohlc_columns)
        
        # Calculate additional features
        result_df['range_down_ticks'] = (result_df['open'] - result_df['low']) / 0.25
        
        return result_df
        
    except Exception as e:
        raise ValueError(f"Error loading {csv_path}: {e}")


def bootstrap_resample(
    original_data: pd.DataFrame,
    n_samples: int,
    random_seed: Optional[int] = None
) -> List[pd.DataFrame]:
    """
    Generate bootstrap resamples by sampling with replacement.
    
    Args:
        original_data: Original DataFrame to resample from
        n_samples: Number of synthetic paths to generate
        random_seed: Random seed for reproducibility
        
    Returns:
        List of synthetic DataFrames (same structure as original)
        
    Example:
        >>> original = load_csv_data("NQH20.csv")
        >>> synthetic_paths = bootstrap_resample(original, n_samples=100)
        >>> print(f"Generated {len(synthetic_paths)} synthetic paths")
    """
    if random_seed is not None:
        np.random.seed(random_seed)
    
    synthetic_paths = []
    n_rows = len(original_data)
    indices = np.arange(n_rows)
    
    print(f"\nGenerating {n_samples} bootstrap samples (each with {n_rows} rows)...")
    
    for i in tqdm(range(n_samples), desc="Bootstrap sampling", unit="sample"):
        # Sample indices with replacement
        sampled_indices = np.random.choice(indices, size=n_rows, replace=True)
        
        # Create synthetic DataFrame
        synthetic_df = original_data.iloc[sampled_indices].copy().reset_index(drop=True)
        synthetic_paths.append(synthetic_df)
    
    return synthetic_paths


def generate_bootstrap_paths(
    base_dir: str,
    n_samples: int = 1000,
    random_seed: Optional[int] = 42,
    save_to_disk: bool = False,
    output_dir: Optional[str] = None
) -> Dict[str, List[pd.DataFrame]]:
    """
    Orchestrate the complete bootstrap path generation process.
    
    Args:
        base_dir: Base directory containing data_export/ folder
        n_samples: Number of bootstrap samples per CSV file
        random_seed: Random seed for reproducibility
        save_to_disk: Whether to save synthetic paths to disk
        output_dir: Directory to save synthetic paths (default: base_dir/bootstrap_outputs)
        
    Returns:
        Dictionary mapping CSV filename to list of synthetic DataFrames
        
    Example:
        >>> all_paths = generate_bootstrap_paths(
        ...     base_dir=".",
        ...     n_samples=100,
        ...     random_seed=42
        ... )
        >>> for csv_name, paths in all_paths.items():
        ...     print(f"{csv_name}: {len(paths)} synthetic paths")
    """
    # Detect CSV files
    csv_files = detect_csv_files(base_dir)
    
    if not csv_files:
        print("No CSV files detected. Aborting.")
        return {}
    
    # Generate bootstrap paths for each CSV
    all_bootstrap_paths = {}
    
    print(f"\n{'='*80}")
    print(f"MONTE CARLO BOOTSTRAP GENERATION")
    print(f"{'='*80}")
    print(f"Base directory: {base_dir}")
    print(f"CSV files detected: {len(csv_files)}")
    print(f"Bootstrap samples per file: {n_samples}")
    print(f"Random seed: {random_seed}")
    print(f"{'='*80}\n")
    
    for csv_path in tqdm(csv_files, desc="Processing CSV files", unit="file"):
        csv_filename = os.path.basename(csv_path)
        
        try:
            # Load original data
            original_df = load_csv_data(csv_path)
            
            # Generate bootstrap samples
            synthetic_paths = bootstrap_resample(
                original_df,
                n_samples=n_samples,
                random_seed=random_seed
            )
            
            all_bootstrap_paths[csv_filename] = synthetic_paths
            
            # Optional: Save to disk
            if save_to_disk:
                if output_dir is None:
                    output_dir = os.path.join(base_dir, "bootstrap_outputs")
                
                os.makedirs(output_dir, exist_ok=True)
                
                for i, path in enumerate(synthetic_paths):
                    output_file = os.path.join(
                        output_dir,
                        f"{csv_filename.replace('.csv', '')}_bootstrap_{i:04d}.csv"
                    )
                    path.to_csv(output_file, index=False)
            
            print(f"  ✓ {csv_filename}: Generated {len(synthetic_paths)} synthetic paths")
            
        except Exception as e:
            print(f"  ✗ {csv_filename}: Error - {e}")
            continue
    
    print(f"\n{'='*80}")
    print(f"BOOTSTRAP GENERATION COMPLETE")
    print(f"{'='*80}")
    print(f"Total CSV files processed: {len(all_bootstrap_paths)}")
    print(f"Total synthetic paths generated: {sum(len(v) for v in all_bootstrap_paths.values())}")
    
    if save_to_disk:
        print(f"Synthetic paths saved to: {output_dir}")
    
    print(f"{'='*80}\n")
    
    return all_bootstrap_paths


def get_bootstrap_statistics(
    original_data: pd.DataFrame,
    synthetic_paths: List[pd.DataFrame],
    metric_func: callable
) -> Dict[str, float]:
    """
    Calculate statistics for a given metric across bootstrap samples.
    
    Args:
        original_data: Original DataFrame
        synthetic_paths: List of synthetic DataFrames from bootstrap
        metric_func: Function that takes a DataFrame and returns a scalar metric
        
    Returns:
        Dictionary with:
            - 'original': Metric value for original data
            - 'mean': Mean across bootstrap samples
            - 'std': Standard deviation across bootstrap samples
            - 'p5': 5th percentile
            - 'p50': Median
            - 'p95': 95th percentile
    """
    # Calculate metric for original data
    original_metric = metric_func(original_data)
    
    # Calculate metrics for all synthetic paths
    synthetic_metrics = [metric_func(path) for path in synthetic_paths]
    
    statistics = {
        'original': original_metric,
        'mean': np.mean(synthetic_metrics),
        'std': np.std(synthetic_metrics),
        'p5': np.percentile(synthetic_metrics, 5),
        'p50': np.percentile(synthetic_metrics, 50),
        'p95': np.percentile(synthetic_metrics, 95)
    }
    
    return statistics


if __name__ == "__main__":
    """
    Example usage of the Monte Carlo Bootstrap module
    """
    import sys
    
    # Set base directory (TermProject folder)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("="*80)
    print("MONTE CARLO BOOTSTRAP MODULE - DEMO")
    print("="*80)
    print(f"Working directory: {base_dir}\n")
    
    # Generate 100 bootstrap samples for each detected CSV file
    # (Use smaller number for demo; typical usage is 1000+)
    n_samples = 100
    
    if len(sys.argv) > 1:
        n_samples = int(sys.argv[1])
    
    print(f"Generating {n_samples} bootstrap samples per CSV file...\n")
    
    # Generate bootstrap paths
    bootstrap_results = generate_bootstrap_paths(
        base_dir=base_dir,
        n_samples=n_samples,
        random_seed=42,
        save_to_disk=False  # Set to True to save to disk
    )
    
    # Print summary
    print("\nSummary:")
    for csv_name, paths in bootstrap_results.items():
        print(f"  {csv_name}: {len(paths)} synthetic paths")
    
    print("\nDone!")