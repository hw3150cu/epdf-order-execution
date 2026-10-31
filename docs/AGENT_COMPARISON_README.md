# Agent vs Our Logic Comparison Tool

This tool compares AI agent trading performance against our limit order optimization strategy.

## Features

1. **Automatic Contract Matching**: Finds the futures contract that overlaps with agent trading period
2. **Dual-Side Trading**: Tests both buy (limit orders below open) and sell (limit orders above open) strategies
3. **Skip Logic**: Highlights bars that don't meet trading criteria
4. **Comprehensive Statistics**: Total PnL, win rate, Sharpe ratio, max drawdown
5. **Visual Comparison**: Plots cumulative PnL curves and performance metrics

## Usage

### Basic Usage

```bash
python compare_agent_vs_logic.py \
    --agent_file data_export/Nasdaq/AIAgent_Nasdaq.csv \
    --data_dir data_export/Nasdaq/
```

### Custom Parameters

```bash
python compare_agent_vs_logic.py \
    --agent_file data_export/Nasdaq/AIAgent_Nasdaq.csv \
    --data_dir data_export/Nasdaq/ \
    --window 120 \
    --penalty 5.0 \
    --max_level 10.0 \
    --tick_size 0.25 \
    --tick_value 50 \
    --warmup 1000
```

### Compare Different Assets

```bash
# Gold
python compare_agent_vs_logic.py \
    --agent_file data_export/Gold/AIAgent_Gold.csv \
    --data_dir data_export/Gold/ \
    --contract_pattern "GC*.csv"

# British Pound
python compare_agent_vs_logic.py \
    --agent_file data_export/GBP\ -\ British\ Pound/AIAgent_GBPUSD.csv \
    --data_dir data_export/GBP\ -\ British\ Pound/ \
    --contract_pattern "BP*.csv"

# Heating Oil
python compare_agent_vs_logic.py \
    --agent_file data_export/HeatingOil/AIAgent_HeatingOil.csv \
    --data_dir data_export/HeatingOil/ \
    --contract_pattern "HO*.csv"
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--agent_file` | Required | Path to agent CSV file |
| `--data_dir` | Required | Directory containing contract data |
| `--contract_pattern` | `*.csv` | Pattern to match contract files |
| `--window` | 60 | Window size for ePDF (bars) |
| `--penalty` | 5.0 | Minimum penalty (ticks) |
| `--max_level` | 10.0 | Maximum level (ticks) |
| `--tick_size` | 0.25 | Price tick size |
| `--tick_value` | 50 | Dollar value per tick |
| `--warmup` | 1000 | Warmup bars before trading |
| `--output_dir` | `results/agent_comparison` | Output directory |

## Input Format

### Agent Data Format
CSV file with columns (no header):
```
date,hour,min,price,cum_vol
20200101,9,30,8000.00,1000
20200101,9,31,8000.25,1020
...
```

### Contract Data Format
OHLC data with columns (from DataLoader):
```
ts,open,high,low,close,vol,...
```

## Output Files

The script generates three files in the output directory:

1. **`comparison_{contract}.csv`**: Bar-by-bar comparison of agent vs our logic
2. **`our_logic_{contract}.csv`**: Detailed our logic results with skip reasons
3. **`summary_{contract}.txt`**: Performance statistics summary
4. **`comparison_plot_{contract}.png`**: Visual comparison plots

## Skip Reasons

Bars that don't meet trading criteria are marked with:
- **"Insufficient ePDF data"**: Not enough historical data to estimate fill probabilities
- **"No orders filled"**: Price didn't reach any limit order levels

These bars are still tracked but don't contribute to savings/PnL.

## Understanding the Results

### PnL Calculation

**Our Logic PnL**: Based on limit order savings
- `PnL = total_savings_ticks * tick_size * tick_value`
- Savings occur when price reaches limit order levels

**Agent PnL**: Based on price changes
- Currently uses simple price change difference
- You may need to adjust based on actual agent strategy

### Statistics

- **Total PnL**: Cumulative profit/loss over the period
- **Win Rate**: Percentage of profitable trades
- **Sharpe Ratio**: Risk-adjusted return (higher is better)
- **Max Drawdown**: Largest peak-to-trough decline (lower is better)

## Examples

### Example 1: Quick Test (1000 bars)

```bash
python compare_agent_vs_logic.py \
    --agent_file data_export/Nasdaq/AIAgent_Nasdaq.csv \
    --data_dir data_export/Nasdaq/ \
    --warmup 200
```

### Example 2: Full Backtest

```bash
python compare_agent_vs_logic.py \
    --agent_file data_export/Nasdaq/AIAgent_Nasdaq.csv \
    --data_dir data_export/Nasdaq/ \
    --window 60 \
    --penalty 5.0 \
    --max_level 10.0 \
    --output_dir results/nasdaq_comparison
```

### Example 3: Multiple Assets Loop

```bash
# Nasdaq
python compare_agent_vs_logic.py \
    --agent_file data_export/Nasdaq/AIAgent_Nasdaq.csv \
    --data_dir data_export/Nasdaq/

# Gold
python compare_agent_vs_logic.py \
    --agent_file data_export/Gold/AIAgent_Gold.csv \
    --data_dir data_export/Gold/

# Heating Oil
python compare_agent_vs_logic.py \
    --agent_file data_export/HeatingOil/AIAgent_HeatingOil.csv \
    --data_dir data_export/HeatingOil/
```

## Troubleshooting

### "No matching contract found"
- Check that contract files exist in the data directory
- Verify date ranges overlap between agent and contract data
- Try adjusting `--contract_pattern` to match your file naming

### "Not enough data"
- Reduce `--warmup` parameter
- Check that contract has enough bars after volume filtering

### Low fill rate
- Increase `--max_level` to allow higher limit order levels
- Reduce `--penalty` to be less conservative
- Check if market conditions are suitable for limit orders

## Notes

1. **Tick Size**: Default is 0.25 for Nasdaq futures. Adjust for other assets:
   - Gold: 0.10
   - GBP: 0.0001 or 0.0002
   - Heating Oil: 0.01

2. **Tick Value**: Default is 50 ($12.50 per tick for NQ). Adjust based on contract multiplier:
   - NQ: 50 ($12.50/tick)
   - GC: 100 ($10.00/tick)
   - BP: 62500 (varies)

3. **Agent PnL**: The current agent PnL calculation is simplified. You may need to implement the actual agent's entry/exit logic for accurate comparison.

## Performance

Expected runtime:
- 1000 bars: ~2-5 minutes
- 5000 bars: ~10-15 minutes
- Full dataset (~60k bars): ~1-2 hours

Runtime depends on:
- Number of bars
- Window size (larger = slower)
- CPU speed