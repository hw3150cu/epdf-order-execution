"""
Test Runner for Phase 1: ePDF Infrastructure
Extracted and modularized from test.py
"""

import matplotlib.pyplot as plt
import os
import numpy as np
import pandas as pd

# Import our new modules
from data_loader import DataLoader
from state_detection import StateDetector
from epdf import ePDFBuilder, build_epdfs
from visualizer import Visualizer


def main():
    """Run Phase 1 test"""
    print("="*80)
    print("PHASE 1: ePDF INFRASTRUCTURE TEST")
    print("="*80)
    
    # Load data
    print("\n1. Loading data...")
    loader = DataLoader()
    df = loader.load_csv('data_export/Nasdaq/NQH20.csv')
    print(f"   Loaded {len(df)} bars")
    
    # Detect states
    print("\n2. Detecting states...")
    detector = StateDetector()
    df = detector.detect_states(df)
    print(f"   States: Low={len(df[df['vol_state']=='Low'])}, "
          f"Med={len(df[df['vol_state']=='Med'])}, "
          f"High={len(df[df['vol_state']=='High'])}")
    
    # Build ePDFs from full dataset
    print("\n3. Building ePDFs...")
    epdfs = build_epdfs(df)
    for state, values in epdfs.items():
        print(f"   {state} state: {len(values)} observations")
    
    # Visualize ePDF histograms
    print("\n4. Plotting ePDF histograms...")
    visualizer = Visualizer()
    
    # Ensure output directory exists
    os.makedirs('results', exist_ok=True)
    
    # Save histogram
    visualizer.plot_epdf_histogram(
        epdfs,
        bins=30,
        save_path='results/epdf_histograms.png'
    )
    print("   Saved to: results/epdf_histograms.png")
    
    # Plot state distribution
    print("\n5. Plotting state distribution...")
    visualizer.plot_state_distribution(
        df,
        save_path='results/state_distribution.png'
    )
    print("   Saved to: results/state_distribution.png")
    
    # Print statistics
    print("\n6. ePDF Statistics:")
    for state in ["Low", "Med", "High"]:
        if len(epdfs[state]) > 0:
            print(f"   {state}:")
            print(f"      Mean: {np.mean(epdfs[state]):.2f}")
            print(f"      Std:  {np.std(epdfs[state]):.2f}")
            print(f"      P50:  {np.percentile(epdfs[state], 50):.2f}")
            print(f"      P80:  {np.percentile(epdfs[state], 80):.2f}")
            print(f"      P95:  {np.percentile(epdfs[state], 95):.2f}")
    
    print("\n" + "="*80)
    print("PHASE 1 COMPLETE!")
    print("="*80)
    print("\nFiles created:")
    print("  - data_loader.py")
    print("   - state_detection.py")
    print("   - epdf.py")
    print("   - visualizer.py")
    print("   - test_epdf.py")
    print("\nResults saved to: results/")
    print("="*80)


if __name__ == "__main__":
    main()