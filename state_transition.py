"""
State Transition Matrix Module

Estimates and uses Markov transition matrices for market state prediction.
Based on stochastic control framework from Zhou's book.

Usage:
    estimator = StateTransitionEstimator(n_states=3)
    P = estimator.fit(df['state'])
    future_dist = estimator.predict_current_state(P, steps=5)
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Tuple, List
from collections import Counter


class StateTransitionEstimator:
    """
    Estimate Markov transition matrix from observed state sequences.
    
    Features:
    - Maximum likelihood estimation
    - Smoothing for rare transitions
    - Multi-step prediction
    - Stationary distribution calculation
    """
    
    def __init__(
        self,
        n_states: int = 3,
        smoothing: float = 0.01,
        state_labels: Optional[List[str]] = None
    ):
        """
        Initialize StateTransitionEstimator.
        
        Args:
            n_states: Number of discrete states
            smoothing: Laplace smoothing parameter
            state_labels: Optional labels for states (e.g., ['low', 'medium', 'high'])
        """
        self.n_states = n_states
        self.smoothing = smoothing
        self.state_labels = state_labels or [f'state_{i}' for i in range(n_states)]
        self.transition_matrix = None
        self.state_counts = None
        
    def fit(self, state_sequence: pd.Series) -> np.ndarray:
        """
        Estimate transition matrix from state sequence.
        
        Args:
            state_sequence: Series of observed states (integers 0 to n_states-1)
            
        Returns:
            Estimated transition matrix P where P[i,j] = P(state_t+1 = j | state_t = i)
        """
        # Initialize count matrix with smoothing
        counts = np.ones((self.n_states, self.n_states)) * self.smoothing
        
        # Count transitions
        for i in range(len(state_sequence) - 1):
            s_from = state_sequence.iloc[i]
            s_to = state_sequence.iloc[i + 1]
            
            # Handle NaN
            if pd.isna(s_from) or pd.isna(s_to):
                continue
                
            s_from = int(s_from)
            s_to = int(s_to)
            
            if 0 <= s_from < self.n_states and 0 <= s_to < self.n_states:
                counts[s_from, s_to] += 1
                
        # Normalize rows to get probabilities
        self.transition_matrix = counts / counts.sum(axis=1, keepdims=True)
        self.state_counts = counts.sum(axis=1)
        
        return self.transition_matrix
    
    def fit_from_returns(
        self,
        returns: pd.Series,
        thresholds: Optional[Tuple[float, float]] = None
    ) -> np.ndarray:
        """
        Estimate transition matrix from return series.
        
        Args:
            returns: Series of returns
            thresholds: Tuple of (low, high) thresholds to discretize
                       Default: (-0.5 std, 0.5 std)
                       
        Returns:
            Estimated transition matrix
        """
        if thresholds is None:
            std = returns.std()
            thresholds = (-0.5 * std, 0.5 * std)
            
        # Discretize returns into states
        def discretize(r):
            if pd.isna(r):
                return np.nan
            if r < thresholds[0]:
                return 0  # low
            elif r > thresholds[1]:
                return 2  # high
            else:
                return 1  # medium
                
        states = returns.apply(discretize)
        return self.fit(states)
    
    def fit_from_volatility(
        self,
        volatility: pd.Series,
        n_bins: int = 3
    ) -> np.ndarray:
        """
        Estimate transition matrix from volatility series.
        
        Args:
            volatility: Series of volatility values
            n_bins: Number of bins (states)
            
        Returns:
            Estimated transition matrix
        """
        # Use quantile-based discretization
        quantiles = np.linspace(0, 1, n_bins + 1)
        bin_edges = volatility.quantile(quantiles).values
        
        def discretize(v):
            if pd.isna(v):
                return np.nan
            for i in range(n_bins):
                if v <= bin_edges[i + 1]:
                    return i
            return n_bins - 1
            
        states = volatility.apply(discretize)
        return self.fit(states)
    
    def predict_next_state(self, current_state: int) -> np.ndarray:
        """
        Get probability distribution over next state.
        
        Args:
            current_state: Current state index
            
        Returns:
            Probability distribution over next states
        """
        if self.transition_matrix is None:
            raise ValueError("Must call fit() first")
            
        return self.transition_matrix[current_state]
    
    def predict_n_steps(self, current_state: int, n_steps: int) -> np.ndarray:
        """
        Predict state distribution after n steps.
        
        Args:
            current_state: Current state index
            n_steps: Number of steps to predict ahead
            
        Returns:
            Probability distribution over states after n steps
        """
        if self.transition_matrix is None:
            raise ValueError("Must call fit() first")
            
        # Start with one-hot distribution
        dist = np.zeros(self.n_states)
        dist[current_state] = 1.0
        
        # Propagate through matrix powers
        P_n = np.linalg.matrix_power(self.transition_matrix, n_steps)
        
        return dist @ P_n
    
    def get_stationary_distribution(self) -> np.ndarray:
        """
        Calculate stationary (equilibrium) distribution.
        
        Returns:
            Stationary distribution over states
        """
        if self.transition_matrix is None:
            raise ValueError("Must call fit() first")
            
        # Find eigenvector with eigenvalue 1
        eigenvalues, eigenvectors = np.linalg.eig(self.transition_matrix.T)
        
        # Find index of eigenvalue closest to 1
        idx = np.argmin(np.abs(eigenvalues - 1))
        
        # Get corresponding eigenvector and normalize
        stationary = np.real(eigenvectors[:, idx])
        stationary = stationary / stationary.sum()
        
        return stationary
    
    def get_expected_holding_time(self, state: int) -> float:
        """
        Get expected number of periods in a state before leaving.
        
        Args:
            state: State index
            
        Returns:
            Expected holding time
        """
        if self.transition_matrix is None:
            raise ValueError("Must call fit() first")
            
        # Expected holding time = 1 / (1 - P[state, state])
        p_stay = self.transition_matrix[state, state]
        if p_stay >= 1:
            return float('inf')
        return 1 / (1 - p_stay)
    
    def get_transition_probabilities(self, from_state: int, to_state: int) -> float:
        """Get probability of transitioning from one state to another."""
        if self.transition_matrix is None:
            raise ValueError("Must call fit() first")
        return self.transition_matrix[from_state, to_state]
    
    def get_summary(self) -> Dict:
        """Get summary statistics of the transition matrix."""
        if self.transition_matrix is None:
            return {"error": "Must call fit() first"}
            
        stationary = self.get_stationary_distribution()
        
        return {
            'n_states': self.n_states,
            'transition_matrix': self.transition_matrix.tolist(),
            'stationary_distribution': stationary.tolist(),
            'expected_holding_times': [
                self.get_expected_holding_time(i) for i in range(self.n_states)
            ],
            'state_labels': self.state_labels
        }


class StatePredictor:
    """
    Predict future market states using transition matrices.
    
    Combines state detection with transition matrix estimation
    for real-time prediction.
    """
    
    def __init__(
        self,
        lookback: int = 60,
        n_states: int = 3,
        update_freq: int = 10
    ):
        """
        Initialize StatePredictor.
        
        Args:
            lookback: Number of periods for estimation
            n_states: Number of discrete states
            update_freq: How often to re-estimate transition matrix
        """
        self.lookback = lookback
        self.n_states = n_states
        self.update_freq = update_freq
        
        self.estimator = StateTransitionEstimator(n_states=n_states)
        self.state_history = []
        self.last_update = 0
        self.is_fitted = False
        
    def update(self, state: int) -> Optional[np.ndarray]:
        """
        Update with new state observation.
        
        Args:
            state: Observed state index
            
        Returns:
            Updated probability distribution over next state (or None if not fitted)
        """
        self.state_history.append(state)
        
        # Keep only lookback period
        if len(self.state_history) > self.lookback:
            self.state_history = self.state_history[-self.lookback:]
            
        # Re-estimate if needed
        if (len(self.state_history) >= 20 and 
            (not self.is_fitted or self.last_update >= self.update_freq)):
            states = pd.Series(self.state_history)
            self.estimator.fit(states)
            self.is_fitted = True
            self.last_update = 0
            
        self.last_update += 1
        
        if self.is_fitted:
            return self.estimator.predict_next_state(state)
        return None
    
    def predict(self, current_state: int, steps: int = 1) -> Optional[np.ndarray]:
        """
        Predict state distribution n steps ahead.
        
        Args:
            current_state: Current state
            steps: Number of steps to predict
            
        Returns:
            Predicted distribution or None if not fitted
        """
        if not self.is_fitted:
            return None
        return self.estimator.predict_n_steps(current_state, steps)
    
    def get_most_likely_state(self, current_state: int, steps: int = 1) -> int:
        """Get most likely state n steps ahead."""
        dist = self.predict(current_state, steps)
        if dist is None:
            return current_state
        return int(np.argmax(dist))


def estimate_transition_from_data(
    df: pd.DataFrame,
    state_col: str = 'prev_state',
    n_states: int = 3
) -> Tuple[np.ndarray, Dict]:
    """
    Convenience function to estimate transition matrix from DataFrame.
    
    Args:
        df: DataFrame with state column
        state_col: Name of state column
        n_states: Number of states
        
    Returns:
        Tuple of (transition_matrix, summary_dict)
    """
    estimator = StateTransitionEstimator(n_states=n_states)
    
    if state_col in df.columns:
        P = estimator.fit(df[state_col])
    else:
        # Try to create states from returns
        if 'close' in df.columns:
            returns = df['close'].pct_change()
            P = estimator.fit_from_returns(returns)
        else:
            raise ValueError(f"Cannot find {state_col} or close column")
            
    return P, estimator.get_summary()


if __name__ == '__main__':
    # Quick test with synthetic data
    np.random.seed(42)
    
    # Create synthetic state sequence
    true_P = np.array([
        [0.7, 0.2, 0.1],
        [0.3, 0.4, 0.3],
        [0.1, 0.3, 0.6]
    ])
    
    states = [0]
    for _ in range(1000):
        s = states[-1]
        next_s = np.random.choice(3, p=true_P[s])
        states.append(next_s)
        
    # Estimate
    estimator = StateTransitionEstimator(n_states=3)
    P_est = estimator.fit(pd.Series(states))
    
    print("True transition matrix:")
    print(true_P)
    print("\nEstimated transition matrix:")
    print(P_est)
    print("\nStationary distribution:")
    print(estimator.get_stationary_distribution())
    print("\nExpected holding times:")
    print(estimator.get_expected_holding_time(0), 
          estimator.get_expected_holding_time(1),
          estimator.get_expected_holding_time(2))