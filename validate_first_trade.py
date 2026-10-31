# Validate first trade calculation
open = 8865.25
high = 8879.0
low = 8863.25
tick_size = 0.25

# Calculate gaps (in price units $)
buy_gap = open - low
sell_gap = high - open

print("GAP CALCULATIONS (in price units $):")
print(f"Buy gap (open - low):  {buy_gap:.2f} = {buy_gap/tick_size:.1f} ticks")
print(f"Sell gap (high - open): {sell_gap:.2f} = {sell_gap/tick_size:.1f} ticks")
print()

# Optimizer levels (in ticks)
limits = [(0.0, 0.33333333), (1.0, 0.33333333), (2.0, 0.33333333)]

print("BUY SIDE SAVINGS:")
print("Comparing buy_gap ($2.00) with levels (in ticks):")
buy_save = 0.0
for level, weight in limits:
    filled = buy_gap >= level
    print(f"  Level {level}t: {buy_gap:.2f} >= {level}? {filled}")
    if filled:
        contribution = weight * level
        buy_save += contribution
        print(f"    → Contributes: {weight:.2f} × {level} = {contribution:.3f}")

print(f"\nTotal buy savings (in tick units): {buy_save:.3f}")
print(f"Converted to ticks (dividing by tick_size): {buy_save/tick_size:.3f} ticks")
print()

print("SELL SIDE SAVINGS:")
print("Comparing sell_gap ($13.75) with levels (in ticks):")
sell_save = 0.0
for level, weight in limits:
    filled = sell_gap >= level
    print(f"  Level {level}t: {sell_gap:.2f} >= {level}? {filled}")
    if filled:
        contribution = weight * level
        sell_save += contribution
        print(f"    → Contributes: {weight:.2f} × {level} = {contribution:.3f}")

print(f"\nTotal sell savings (in tick units): {sell_save:.3f}")
print(f"Converted to ticks (dividing by tick_size): {sell_save/tick_size:.3f} ticks")
print()

total_save = (buy_save + sell_save) / tick_size
print(f"TOTAL SAVINGS:")
print(f"  Buy:  {buy_save/tick_size:.3f} ticks")
print(f"  Sell: {sell_save/tick_size:.3f} ticks")
print(f"  Total: {total_save:.3f} ticks")