import os
import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm


        for file in files:
            if file.endswith('.csv'):
                file_path = os.path.join(root, file)
                filename_no_ext = file.replace('.csv', '')
                
                # Check if filename length is 9 (8 characters + .csv)
                if len(file) == 9:
                    # Read CSV file (no header)
                    try:
                        df = pd.read_csv(file_path, header=None)
                        
                        # Check if DataFrame has at least 5 columns for OHLC data
                        # Structure: date(0), Open(1), High(2), Low(3), Close(4), volume(5)
                        if df.shape[1] < 5:
                            print(f"Skipping {file}: has only {df.shape[1]} columns, need at least 5 for OHLC analysis")
                            continue
                        
                        # Extract OHLC columns (indices 1, 2, 3, 4 - 0-indexed)
                        # Based on data: date, Open, High, Low, Close = columns 0, 1, 2, 3, 4
                        ohlc_data = df.iloc[:, 1:5].values  # Open, High, Low, Close
                        
                        # Check if OHLC are identical across all rows
                        ohlc_identical = np.all(ohlc_data == ohlc_data[0])
                        
                        # Calculate ratios relative to Open (column 0)
                        open_vals = ohlc_data[:, 0]
                        # Avoid division by zero
                        open_vals = np.where(open_vals == 0, np.nan, open_vals)
                        
                        high_ratios = ohlc_data[:, 1] / open_vals
                        low_ratios = ohlc_data[:, 2] / open_vals
                        close_ratios = ohlc_data[:, 3] / open_vals
                        
                        # Check if ratios are constant (allowing for floating point precision)
                        tolerance = 1e-10
                        high_ratio_constant = np.allclose(high_ratios, high_ratios[0], rtol=tolerance, atol=tolerance, equal_nan=True)
                        low_ratio_constant = np.allclose(low_ratios, low_ratios[0], rtol=tolerance, atol=tolerance, equal_nan=True)
                        close_ratio_constant = np.allclose(close_ratios, close_ratios[0], rtol=tolerance, atol=tolerance, equal_nan=True)
                        
                        ratios_constant = high_ratio_constant and low_ratio_constant and close_ratio_constant
                        
                        # Store results
                        result = {
                            'Filename': file,
                            'Path': os.path.relpath(file_path, base_dir),
                            'Total Rows': len(df),
                            'OHLC Identical': ohlc_identical,
                            'OHLC Ratios Constant': ratios_constant,
                            'H/O Ratio (mean)': round(np.nanmean(high_ratios), 6),
                            'L/O Ratio (mean)': round(np.nanmean(low_ratios), 6),
                            'C/O Ratio (mean)': round(np.nanmean(close_ratios), 6)
                        }
                        results.append(result)
                        
                    except Exception as e:
                        print(f"Error reading {file}: {e}")
    
    return results

def print_summary_table(results):
    """Print a formatted summary table."""
    if not results:
        print("No CSV files with 9-character filenames found.")
        return
    
    # Create DataFrame for nice formatting
    df_results = pd.DataFrame(results)
    
    print("\n" + "="*100)
    print("SUMMARY TABLE - CSV Files with 9-character filenames")
    print("="*100)
    print(df_results.to_string(index=False))
    print("="*100)
    
    # Print statistics
    total_files = len(results)
    identical_ohlc = sum(1 for r in results if r['OHLC Identical'])
    constant_ratios = sum(1 for r in results if r['OHLC Ratios Constant'])
    
    print(f"\nStatistics:")
    print(f"  Total files with 9-character names: {total_files}")
    print(f"  Files with identical OHLC values: {identical_ohlc} ({identical_ohlc/total_files*100:.1f}%)")
    print(f"  Files with constant OHLC ratios: {constant_ratios} ({constant_ratios/total_files*100:.1f}%)")
    
    # List files with constant ratios
    if constant_ratios > 0:
        print(f"\nFiles with constant OHLC ratios:")
        for r in results:
            if r['OHLC Ratios Constant']:
                print(f"  - {r['Filename']}: H/O={r['H/O Ratio (mean)']}, L/O={r['L/O Ratio (mean)']}, C/O={r['C/O Ratio (mean)']}")

if __name__ == "__main__":
    # Use the data_export folder
    base_dir = "os.environ.get("ORDER_DATA_ROOT", "data_export")"
    
    print(f"Analyzing CSV files in: {base_dir}")
    print("Looking for files with 9-character filenames (e.g., VGH22.csv)")
    
    results = analyze_csv_files(base_dir)
    print_summary_table(results)