import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller
from typing import Tuple, Optional, Dict
import logging

class KalmanFilterReg:
    """
    Simple Kalman Filter for dynamic Beta estimation.
    State Space Model:
    y_t = beta_t * x_t + e_t (Observation)
    beta_t = beta_{t-1} + w_t (State Transition)
    """
    def __init__(self, delta=1e-5, R=1e-3):
        self.delta = delta # Process noise variance
        self.R = R # Measurement noise variance
        self.P = np.eye(2) # Covariance matrix
        self.beta = np.zeros(2) # State vector [beta, alpha] (slope, intercept)

    def update(self, x, y):
        # State transition (Random Walk, so prior = posterior from last step)
        # Prediction step (simplified for random walk beta)
        P = self.P + self.delta 
        
        # Observation matrix H = [x, 1]
        H = np.array([x, 1.0])
        
        # Innovation
        y_hat = H @ self.beta
        error = y - y_hat
        
        # Kalman Gain
        S = H @ P @ H.T + self.R
        K = P @ H.T / S
        
        # Update State
        self.beta = self.beta + K * error
        
        # Update Covariance
        self.P = (np.eye(2) - np.outer(K, H)) @ P
        
        return self.beta[0] # Return slope (beta)

class FinancialMetrics:
    
    @staticmethod
    def calculate_spread(series1: pd.Series, series2: pd.Series, hedge_ratio: float) -> pd.Series:
        """
        Spread = Price1 - (HedgeRatio * Price2)
        """
        # Align timestamps via inner join to ensure we compare same-time data
        # Assuming series index is timestamp
        df = pd.DataFrame({'p1': series1, 'p2': series2}).dropna()
        return df['p1'] - (hedge_ratio * df['p2'])

    @staticmethod
    def calculate_zscore(spread: pd.Series, window: int) -> pd.Series:
        """
        Z = (Spread - RollingMean) / RollingStd
        """
        roll = spread.rolling(window=window)
        mean = roll.mean()
        std = roll.std()
        return (spread - mean) / std

    @staticmethod
    def calculate_ols_hedge_ratio(series_y: pd.Series, series_x: pd.Series) -> Optional[float]:
        """
        Regress Y on X to find Beta (Hedge Ratio).
        Y = Beta * X + Alpha
        """
        try:
            df = pd.DataFrame({'y': series_y, 'x': series_x}).dropna()
            if len(df) < 20: # Minimal data check
                return None
            
            X = sm.add_constant(df['x'])
            model = sm.OLS(df['y'], X).fit()
            return model.params['x']
        except Exception as e:
            logging.error(f"OLS Error: {e}")
            return None

    @staticmethod
    def calculate_robust_hedge_ratio(series_y: pd.Series, series_x: pd.Series) -> Optional[float]:
        """
        Uses Huber Regression (Robust Linear Model) to reduce outlier influence.
        """
        try:
            df = pd.DataFrame({'y': series_y, 'x': series_x}).dropna()
            if len(df) < 20:
                return None
            
            X = sm.add_constant(df['x'])
            # M-estimator with Huber weights
            model = sm.RLM(df['y'], X, M=sm.robust.norms.HuberT()).fit()
            return model.params['x']
        except Exception as e:
            logging.error(f"Robust Reg Error: {e}")
            return None
    
    @staticmethod
    def run_kalman_filter(series_y: pd.Series, series_x: pd.Series) -> pd.Series:
        """
        Returns a rolling Beta series using a Kalman Filter.
        """
        kf = KalmanFilterReg(delta=1e-5, R=1e-3)
        betas = []
        # Iterate and update
        for x, y in zip(series_x, series_y):
            b = kf.update(x, y)
            betas.append(b)
        
        return pd.Series(betas, index=series_y.index)

    @staticmethod
    def backtest_mean_reversion(zscores: pd.Series, prices: pd.Series, entry_thresh=2.0, exit_thresh=0.0):
        """
        Simple Vectorized Backtest.
        Strategy: Long when Z < -entry, Short when Z > entry. Exit when Z crosses 0.
        Note: This is a signal-only backtest for visualization.
        """
        signals = pd.Series(0, index=zscores.index)
        positions = pd.Series(0, index=zscores.index)
        
        # 1 = Long Spread, -1 = Short Spread
        signals[zscores > entry_thresh] = -1
        signals[zscores < -entry_thresh] = 1
        
        # Generate simple positions (filling forward signals)
        # This is a simplification. For a real backtest we need stateful loops usually.
        # Stateful loop for correctness:
        curr_pos = 0
        pos_list = []
        for z in zscores:
            if curr_pos == 0:
                if z > entry_thresh: curr_pos = -1
                elif z < -entry_thresh: curr_pos = 1
            elif curr_pos == 1:
                if z >= exit_thresh: curr_pos = 0
            elif curr_pos == -1:
                if z <= -exit_thresh: curr_pos = 0
            pos_list.append(curr_pos)
            
        positions = pd.Series(pos_list, index=zscores.index)
        
        # PnL approx: Spread Return * Position
        # But we don't have spread return easily here, so we return positions for the UI to plot overlay.
        return positions

    @staticmethod
    def perform_adf_test(series: pd.Series) -> Dict[str, float]:
        """
        Returns stats from Augmented Dickey-Fuller test
        """
        try:
            # Drop NAs
            s = series.dropna()
            if len(s) < 20: 
                return {"p_value": 1.0, "test_stat": 0.0}

            result = adfuller(s)
            return {
                "test_stat": result[0],
                "p_value": result[1],
                "used_lag": result[2],
                "n_obs": result[3]
            }
        except Exception as e:
            logging.error(f"ADF Error: {e}")
            return {"p_value": 1.0, "test_stat": 0.0}

    @staticmethod
    def calculate_rolling_correlation(s1: pd.Series, s2: pd.Series, window: int) -> pd.Series:
        return s1.rolling(window).corr(s2)
