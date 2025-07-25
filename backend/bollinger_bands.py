"""
Bollinger Bands Calculator module.
Uses raw data from the database to calculate Bollinger Bands indicator and saves it to the database.

Bollinger Bands are a volatility indicator that helps identify overbought and oversold conditions,
potential trend reversals, or breakouts.

A Bollinger Band consists of:
- Middle Band: A 20-period simple moving average (SMA)
- Upper Band: 20 SMA + 2 standard deviations
- Lower Band: 20 SMA - 2 standard deviations

When volatility increases, the bands widen. When volatility decreases, they contract.
"""
import pandas as pd
import sqlite3
import numpy as np
from typing import Optional


class BollingerBandsCalculator:
    """Calculates Bollinger Bands indicator from raw data."""
    
    def __init__(self, raw_db_path: str = 'data/raw_market_data.db', bollinger_db_path: str = 'data/bollinger_bands_data.db'):
        # Ensure we use the correct database paths relative to project root
        import os
        if not os.path.isabs(raw_db_path) and not raw_db_path.startswith('../'):
            # If running from backend directory, adjust path to parent directory
            if os.path.basename(os.getcwd()) == 'backend':
                raw_db_path = '../' + raw_db_path
                bollinger_db_path = '../' + bollinger_db_path
        self.raw_db_path = raw_db_path
        self.bollinger_db_path = bollinger_db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with Bollinger Bands table if it doesn't exist."""
        with sqlite3.connect(self.bollinger_db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS bollinger_bands_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    bb_upper REAL,
                    bb_lower REAL,
                    bb_middle REAL,
                    bb_width REAL,
                    bb_percent REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timeframe, timestamp)
                )
            ''')
            conn.commit()
    
    def fetch_raw_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Fetch raw OHLCV data from the database."""
        query = '''
            SELECT timestamp, open, high, low, close, volume
            FROM raw_data
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp ASC
        '''
        with sqlite3.connect(self.raw_db_path) as conn:
            return pd.read_sql(query, conn, params=(symbol, timeframe))

    def calculate_bollinger_bands(self, df: pd.DataFrame, window: int = 20, std_dev: float = 2) -> pd.DataFrame:
        """
        Calculate Bollinger Bands on data.
        
        Parameters:
        - df: DataFrame with OHLCV data
        - window: Period for moving average (default: 20)
        - std_dev: Number of standard deviations (default: 2)
        
        Returns:
        - DataFrame with Bollinger Bands indicators added
        """
        # Calculate the middle band (Simple Moving Average)
        df['bb_middle'] = df['close'].rolling(window=window, min_periods=1).mean()
        
        # Calculate the standard deviation
        df['bb_std'] = df['close'].rolling(window=window, min_periods=1).std(ddof=0)
        
        # Calculate upper and lower bands
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * std_dev)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * std_dev)
        
        # Calculate additional indicators
        # Bollinger Band Width (measures volatility)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        
        # Bollinger Band Percent (%B) - shows where price is relative to the bands
        # %B = (Close - Lower Band) / (Upper Band - Lower Band)
        # Values above 1 indicate price is above upper band
        # Values below 0 indicate price is below lower band
        df['bb_percent'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # Handle edge cases where bands might be equal (no volatility)
        df['bb_percent'] = df['bb_percent'].fillna(0.5)  # Default to middle if no volatility
        
        return df

    def save_bollinger_bands_data(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """Save calculated Bollinger Bands data to the database."""
        df_to_save = df[
            ['timestamp', 'open', 'high', 'low', 'close', 'volume', 
             'bb_upper', 'bb_lower', 'bb_middle', 'bb_width', 'bb_percent']
        ].copy()
        df_to_save['symbol'] = symbol
        df_to_save['timeframe'] = timeframe
        
        # Reorder columns to match database schema
        df_to_save = df_to_save[
            ['symbol', 'timeframe', 'timestamp', 'open', 'high', 'low', 'close', 'volume', 
             'bb_upper', 'bb_lower', 'bb_middle', 'bb_width', 'bb_percent']
        ]
        
        try:
            with sqlite3.connect(self.bollinger_db_path) as conn:
                cursor = conn.cursor()
                inserted = 0
                for _, row in df_to_save.iterrows():
                    cursor.execute('''
                        INSERT OR REPLACE INTO bollinger_bands_data 
                        (symbol, timeframe, timestamp, open, high, low, close, volume, 
                         bb_upper, bb_lower, bb_middle, bb_width, bb_percent)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', tuple(row))
                    inserted += 1
                conn.commit()
                print(f"[INFO] Saved {inserted} Bollinger Bands records for {symbol} ({timeframe})")
        except Exception as e:
            print(f"[ERROR] Failed to save Bollinger Bands data for {symbol}: {e}")

    def get_bollinger_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on Bollinger Bands.
        
        Common signals:
        - Price touching/crossing upper band: Potential sell signal (overbought)
        - Price touching/crossing lower band: Potential buy signal (oversold)
        - Bollinger Band squeeze: Low volatility, potential breakout coming
        - Bollinger Band expansion: High volatility, trend continuation
        """
        df = df.copy()
        
        # Initialize signal column
        df['bb_signal'] = 'hold'
        
        # Buy signals (oversold conditions)
        buy_condition = (
            (df['close'] <= df['bb_lower']) |  # Price at or below lower band
            (df['bb_percent'] <= 0.2)  # %B indicates oversold
        )
        df.loc[buy_condition, 'bb_signal'] = 'buy'
        
        # Sell signals (overbought conditions)
        sell_condition = (
            (df['close'] >= df['bb_upper']) |  # Price at or above upper band
            (df['bb_percent'] >= 0.8)  # %B indicates overbought
        )
        df.loc[sell_condition, 'bb_signal'] = 'sell'
        
        # Squeeze detection (low volatility)
        df['bb_squeeze'] = df['bb_width'] < df['bb_width'].rolling(window=20, min_periods=1).quantile(0.25)
        
        return df

    def analyze_bollinger_patterns(self, df: pd.DataFrame) -> dict:
        """Analyze current Bollinger Bands patterns and provide insights."""
        if df.empty:
            return {}
        
        latest = df.iloc[-1]
        recent_data = df.tail(20)  # Last 20 periods
        
        analysis = {
            'current_position': self._get_position_description(latest['bb_percent']),
            'volatility_state': self._get_volatility_state(latest['bb_width'], recent_data['bb_width'].mean()),
            'recent_signal': latest.get('bb_signal', 'hold'),
            'squeeze_active': latest.get('bb_squeeze', False),
            'price_vs_bands': {
                'close': latest['close'],
                'upper_band': latest['bb_upper'],
                'middle_band': latest['bb_middle'],
                'lower_band': latest['bb_lower'],
                'percent_b': latest['bb_percent']
            }
        }
        
        return analysis
    
    def _get_position_description(self, bb_percent: float) -> str:
        """Get descriptive text for current price position relative to bands."""
        if bb_percent >= 1:
            return "Above upper band (very overbought)"
        elif bb_percent >= 0.8:
            return "Near upper band (overbought)"
        elif bb_percent >= 0.6:
            return "Above middle (bullish)"
        elif bb_percent >= 0.4:
            return "Around middle (neutral)"
        elif bb_percent >= 0.2:
            return "Below middle (bearish)"
        elif bb_percent > 0:
            return "Near lower band (oversold)"
        else:
            return "Below lower band (very oversold)"
    
    def _get_volatility_state(self, current_width: float, avg_width: float) -> str:
        """Get descriptive text for current volatility state."""
        ratio = current_width / avg_width if avg_width > 0 else 1
        
        if ratio >= 1.5:
            return "High volatility (bands expanding)"
        elif ratio >= 1.2:
            return "Above average volatility"
        elif ratio >= 0.8:
            return "Normal volatility"
        elif ratio >= 0.6:
            return "Below average volatility"
        else:
            return "Low volatility (potential squeeze)"


def main():
    """Main function to calculate and save Bollinger Bands data for multiple symbols and timeframes."""
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'SOL/BTC', 'ETH/BTC']
    timeframes = ['4h', '1d']

    calculator = BollingerBandsCalculator()

    for symbol in symbols:
        for timeframe in timeframes:
            print(f"\n[CALCULATING] Bollinger Bands for {symbol} - {timeframe.upper()}")
            df_raw = calculator.fetch_raw_data(symbol, timeframe)
            if df_raw.empty:
                print(f"[INFO] No raw data available for {symbol} ({timeframe})")
                continue
            
            # Calculate Bollinger Bands
            df_bb = calculator.calculate_bollinger_bands(df_raw)
            
            # Add trading signals
            df_bb = calculator.get_bollinger_signals(df_bb)
            
            # Save to database
            calculator.save_bollinger_bands_data(df_bb, symbol, timeframe)
            
            # Print analysis for the latest data
            analysis = calculator.analyze_bollinger_patterns(df_bb)
            if analysis:
                print(f"[ANALYSIS] Current position: {analysis['current_position']}")
                print(f"[ANALYSIS] Volatility: {analysis['volatility_state']}")
                print(f"[ANALYSIS] Recent signal: {analysis['recent_signal']}")


if __name__ == '__main__':
    main()
