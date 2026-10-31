#!/usr/bin/env python3
"""Compare trust-constr vs multi-start SLSQP optimization methods"""

from data_loader import DataLoader
from strategies_optimized_final import DiscreteStrategyOptimizer
import time

print('Comparing trust-constr vs multi-start SLSQP...')
print('=' * 60)

# Load data
loader = DataLoader('data_export/Nasdaq/', max_bars=500)
data = loader.load_data()

# Initialize
optimizer = DiscreteStrategyOptimizer(min_penalty=5.0, max_level=10.0)
optimizer.build_epdf(data, window=60)

# Test on specific bars
test_bars = [150, 160, 170, 180, 190]

print('\nBar   Method      Time(ms)  ObjVal   Levels                 Weights')
print('-' * 75)

tc_times = []
ms_times = []
obj_diffs = []

for bar in test_bars:
    # Get historical data
    window_data = data.iloc[bar-60:bar].copy()
    
    # Test trust-constr
    start = time.time()
    levels, weights, obj = optimizer.optimize_trust_constr(window_data)
    tc_time = (time.time() - start) * 1000
    tc_times.append(tc_time)
    
    print(f'{bar}  trust-constr  {tc_time:7.1f}  {obj:6.3f}  {str(list(levels))[:22]:22s}  {str(list(weights))[:22]}')
    
    # Test multi-start SLSQP
    start = time.time()
    levels2, weights2, obj2 = optimizer.optimize_multi_start_slsqp(window_data)
    ms_time = (time.time() - start) * 1000
    ms_times.append(ms_time)
    obj_diff = abs(obj - obj2)
    obj_diffs.append(obj_diff)
    
    print(f'     multi-start   {ms_time:7.1f}  {obj2:6.3f}  {str(list(levels2))[:22]:22s}  {str(list(weights2))[:22]}')
    print(f'     diff:         {ms_time/tc_time:5.1f}x faster, obj diff: {obj_diff:.4f}')
    print()

print('=' * 75)
print(f'AVERAGE trust-constr:   {sum(tc_times)/len(tc_times):7.1f}ms')
print(f'AVERAGE multi-start:    {sum(ms_times)/len(ms_times):7.1f}ms')
print(f'SPEEDUP:                {sum(tc_times)/sum(ms_times):5.1f}x')
print(f'AVG OBJ DIFF:           {sum(obj_diffs)/len(obj_diffs):.4f}')
print('=' * 75)