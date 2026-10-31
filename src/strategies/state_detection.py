"""
State Detection Module
EWMA/EWMV volatility state detection
"""

import pandas as pd
import numpy as np


class StateDetector:
    """Calculate EWMA/EWMV detect volatility states (2-regime)"""
    
    def __init__(self, m: int = 20, thresh: float = 2.5):
        """Initialize state detector
        
        Args:
            m: EWMA/EWMV lookback period
            thresh: Volatility threshold (use des 2.5 for NQ)
        """
        self.m = m
        self.thresh = thresh
        self.lam = 1 - (2 / (m + 1))
    
    def detect_states(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate EWMA/EWMV and detect states"""
        df = df.copy()
        
        sum_w, sum_wx, sum_wss = 0, 0, 0
        states = []
        ewmas = []
        ewmvs = []
        
        for i in range(len(df)):
            val = df['range_dn_ticks'].iloc[i]
            
            if i == 0:
                ewma, ewmv = val, 0
                sum_w, sum_wx = 1, val
            else:
                sum_w = self.lam * sum_w + 1
                sum_wx = self.lam * sum_wx + val
                ewma = sum_wx / sum_w
                sum_wss = self.lam * sum_wss + (val - ewma)**2
                ewmv = np.sqrt(sum_wss / sum_w)
            
            # 2-regime classification: Low vs High
            state = "Low" if ewmv < self.thresh else "High"
            ewmas.append(ewma)
            ewmvs.append(ewmv)
            states.append(state)
        
        df['ewma'] = ewmas
        df['ewmv'] = ewmvs
        df['vol_state'] = states
        df['prev_state'] = df['vol_state'].shift(1)  # Lag to avoid look-ahead
        
        return df