"""Test agent data matching with our data"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

print("="*70)
print("TEST: AGENT DATA MATCHING")
print("="*70)

# Load agent data
print("\n1. Loading agent data...")
agent_df = pd.read_csv('data_export/Nasdaq/AIAgent_Nasdaq.csv',
                       header=None,
                       names=['date', 'hour', 'min', 'price', 'cum_vol'])

# Create datetime for agent data
start_date = datetime(1900, 1, 1)
agent_df['datetime'] = agent_df.apply(
    lambda row: start_date + timedelta(days=int(row['date'])-2,
                                       hours=int(row['hour']),
                                       minutes=int(row['min'])),
    axis=1
)

# Calculate bar volume
agent_df['vol'] = agent_df['cum_vol'].diff(-1).abs().fillna(0)

# Set datetime as index and sort
agent_df = agent_df.set_index('datetime').sort_index()

print(f"   Agent data: {len(agent_df)} bars")
print(f"   Date range: {agent_df.index.min()} to {agent_df.index.max()}")
print(f"   Sample bars:")
print(agent_df[['price', 'vol']].head(10))

# Load our data
print("\n2. Loading our data...")
df = pd.read_csv('data_export/Nasdaq/NQH20.csv',
                 header=None,
                 names=['ts', 'open', 'high', 'low', 'close', 'vol'])
df['datetime'] = pd.to_datetime(df['ts'], format='%Y.%m.%d.%H:%M:%S')
df = df.set_index('datetime').sort_index()

print(f"   Our data: {len(df)} bars (raw)")
print(f"   Date range: {df.index.min()} to {df.index.max()}")

# Resample to 5-minute intervals
print("\n3. Resampling our data to 5-minute bars...")
df_5min = df.resample('5T').agg({
    'open': 'first',
    'high': 'max',
    'low': 'min',
    'close': 'last',
    'vol': 'sum'
}).dropna()

print(f"   Resampled data: {len(df_5min)} bars (5-minute)")
print(f"   Date range: {df_5min.index.min()} to {df_5min.index.max()}")
print(f"   Sample bars:")
print(df_5min[['open', 'high', 'low', 'close', 'vol']].head(10))

# Match timestamps
print("\n4. Matching agent timestamps with our data...")
matched_df = agent_df.join(df_5min, how='left', rsuffix='_ours')

print(f"   Total agent bars: {len(agent_df)}")
print(f"   Matched bars: {matched_df['open'].notna().sum()}")
print(f"   Unmatched bars: {matched_df['open'].isna().sum()}")

# Show unmatched examples
unmatched = matched_df[matched_df['open'].isna()]
if len(unmatched) > 0:
    print(f"\n   First 10 unmatched timestamps:")
    print(unmatched[['price', 'vol']].head(10))

# Show matched examples
matched = matched_df[matched_df['open'].notna()]
if len(matched) > 0:
    print(f"\n   First 10 matched timestamps:")
    print(matched[['price', 'open', 'vol', 'vol_ours']].head(10))

# Filter to common date range
print("\n5. Filtering to common date range...")
start_date_common = max(agent_df.index.min(), df_5min.index.min())
end_date_common = min(agent_df.index.max(), df_5min.index.max())

agent_filtered = agent_df[(agent_df.index >= start_date_common) &
                         (agent_df.index <= end_date_common)]
ours_filtered = df_5min[(df_5min.index >= start_date_common) &
                       (df_5min.index <= end_date_common)]

print(f"   Common date range: {start_date_common} to {end_date_common}")
print(f"   Agent bars in range: {len(agent_filtered)}")
print(f"   Our bars in range: {len(ours_filtered)}")

# Final match
matched_final = agent_filtered.join(ours_filtered, how='left', rsuffix='_ours')
matched_count = matched_final['open'].notna().sum()
print(f"   Matched bars: {matched_count} / {len(agent_filtered)} ({matched_count/len(agent_filtered)*100:.1f}%)")

print("\n" + "="*70)
print("TEST COMPLETE")
print("="*70)