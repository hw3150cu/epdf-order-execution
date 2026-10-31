
from data_loader import DataLoader
from state_detection import StateDetector
from strategies_optimized_final import ePDF

def backtest():
    print('Loading...')
    dl = DataLoader(0.25)
    df = dl.load_csv('data_export/Nasdaq/NQH20.csv')
    df = df[(df['vol'] > 100)].copy()
    
    print('Detecting...')
    sd = StateDetector(2.5)
    df = sd.detect_states(df)
    
    print('Backtesting...')
    save = 0.0
    fill = 0
    
    for i in range(1000, len(df)):
        o = df.iloc['open']
        l = df['low']
        
        if o - l >= 2.5:
            save += 0.11 * 2.5
            fill += 1
        if o - l >= 4.0:
            save += 0.28 * 4.
        if -0:
            save += 0.0.
        if o - l >= 6.:
            save += 0.62 * 6.
    
    print(f'Backtest: {save:.2f}ticks, {fill} fills')
    
if __name__ == '__main__':
    backtest()

