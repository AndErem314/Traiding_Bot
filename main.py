"""
Main runner script for the Trading Bot.
Coordinates data collection and Gaussian Channel calculation.
"""
import sys
import argparse
from datetime import datetime

from data_fetcher import RawDataCollector
from gaussian_channel import GaussianChannelCalculator


def collect_raw_data(symbols, timeframes, start_time=None):
    """Collect raw data for specified symbols and timeframes."""
    print("=== COLLECTING RAW DATA ===")
    collector = RawDataCollector()
    
    for symbol in symbols:
        for timeframe in timeframes:
            collector.collect_data(symbol, timeframe, start_time=start_time)


def calculate_gaussian_channels(symbols, timeframes):
    """Calculate Gaussian Channel indicators for specified symbols and timeframes."""
    print("\n=== CALCULATING GAUSSIAN CHANNELS ===")
    calculator = GaussianChannelCalculator()
    
    for symbol in symbols:
        for timeframe in timeframes:
            print(f"\n[CALCULATING] Gaussian Channel for {symbol} - {timeframe.upper()}")
            df_raw = calculator.fetch_raw_data(symbol, timeframe)
            if df_raw.empty:
                print(f"[INFO] No raw data available for {symbol} ({timeframe})")
                continue
            df_gc = calculator.calculate_gaussian_channel(df_raw)
            calculator.save_gaussian_channel_data(df_gc, symbol, timeframe)


def main():
    """Main function with command line arguments."""
    parser = argparse.ArgumentParser(description='Trading Bot - Data Collection and Analysis')
    parser.add_argument('--mode', choices=['collect', 'calculate', 'both'], 
                       default='both', help='Mode of operation')
    parser.add_argument('--symbols', nargs='+', 
                       default=['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
                       help='Symbols to process')
    parser.add_argument('--timeframes', nargs='+', 
                       default=['4h', '1d'],
                       help='Timeframes to process')
    parser.add_argument('--start-date', type=str, default='2021-01-01',
                       help='Start date for data collection (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # Parse start date
    start_time = int(datetime.strptime(args.start_date, '%Y-%m-%d').timestamp() * 1000)
    
    print(f"Trading Bot starting...")
    print(f"Mode: {args.mode}")
    print(f"Symbols: {args.symbols}")
    print(f"Timeframes: {args.timeframes}")
    print(f"Start date: {args.start_date}")
    
    try:
        if args.mode in ['collect', 'both']:
            collect_raw_data(args.symbols, args.timeframes, start_time)
        
        if args.mode in ['calculate', 'both']:
            calculate_gaussian_channels(args.symbols, args.timeframes)
            
        print("\n=== COMPLETED SUCCESSFULLY ===")
        
    except KeyboardInterrupt:
        print("\n[INFO] Process interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] An error occurred: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
