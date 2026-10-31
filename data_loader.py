"""
Data Loader Module
Load and preprocess OHLC data for ePDF construction
"""

import pandas as pd
import numpy as np
from typing import Optional, List


class DataLoader:
    """Load and preprocess OHLC data for backtesting"""
    
    def __init__(self, tick: float = 0.25, tick_size: float = None):
        """Initialize data loader"""
        # Support both parameter names for compatibility
        self.tick = tick
        self.tick_size = tick_size if tick_size is not None else tick
    
    def load_csv(self, file_path: str) -> pd.DataFrame:
        """Load CSV file and return OHLC DataFrame"""
        df = pd.read_csv(file_path, header=None)
        df.columns = ['ts', 'open', 'high', 'low', 'close', 'vol']
        df['range_dn_ticks'] = (df['open'] - df['low']) / self.tick_size  # For BUY orders
        df['range_up_ticks'] = (df['high'] - df['open']) / self.tick_size  # For SELL orders
        return df
    
    def load_contracts(self, contract_files: List[str]) -> dict:
        """Load multiple contract files"""
        contracts = {}
        for file_path in contract_files:
            contract_name = file_path.split('/')[-1].replace('.csv', '')
            contracts[contract_name] = self.load_csv(file_path)
        return contracts