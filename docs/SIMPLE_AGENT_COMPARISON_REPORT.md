# Agent vs Our Strategy - 直接对比报告

**IEOR 4703 Term Project 2**

**Generated**: 2026-04-17  
**Status**: ✅ Complete  
**Note**: HeatingOil temporarily excluded (data quality issue)

---

## 🎯 对比设计

**简单直接的对比**：
- 对于 Agent 的**每一笔交易**
- 我们用**同样的交易量**
- 在**同一个 bar**执行
- 对比谁的执行价格更好

**我们的策略**：
```python
# 限价单 = Open ± 1 tick
if direction == 'buy':
    limit_price = open - 1 * tick_size
    if low <= limit_price:
        fill at limit_price  # 成交
    else:
        fill at open  # 未成交，市价执行
else:  # sell
    limit_price = open + 1 * tick_size
    if high >= limit_price:
        fill at limit_price
    else:
        fill at open
```

---

## 📊 核心结果

| 资产 | 交易数 | Agent 总节省 | Our 总节省 | **改进值** | **胜率** | 填充率 |
|------|--------|------------|-----------|-----------|---------|--------|
| **Nasdaq** | 2,164 | +2,608 | +1,451 | **-1,157** | 53.9% | 67.1% |
| **Gold** | 1,276 | -2,424 | +778 | **+3,202** ✅ | 52.4% | 61.0% |
| **German Bunds** | 613 | -1,245 | +310 | **+1,555** ✅ | 50.9% | 50.6% |
| **GBP** | 504 | +18,200 | +96 | **-18,104** ❌ | 50.8% | 19.0% |
| **JPY** | 804 | +201 | +571 | **+370** ✅ | **58.8%** | 71.0% |
| **EuroStoxx** | 212 | +1,448 | +138 | **-1,310** | 55.7% | 65.1% |

**总计**:
- 交易数：**5,573**
- 总改进：**-15,444 ticks** (Agent 更好)
- 平均胜率：**53.7%**

---

## 🔍 关键发现

### 1. 互有胜负（53.7% 胜率）

**我们跑赢 Agent 的资产**：
- ✅ JPY: +370 ticks (58.8% 胜率)
- ✅ Gold: +3,202 ticks (52.4% 胜率)
- ✅ German Bunds: +1,555 ticks (50.9% 胜率)

**Agent 跑赢我们的资产**：
- ❌ GBP: -18,104 ticks (但胜率仍有 50.8%!)
- ❌ Nasdaq: -1,157 ticks
- ❌ EuroStoxx: -1,310 ticks

### 2. 胜率 vs 改进值的差异

**关键洞察**：胜率高 ≠ 总改进值高！

| 资产 | 胜率 | 总改进 | 解释 |
|------|------|--------|------|
| JPY | **58.8%** | +370 | 胜率高，但每笔改进小 |
| Gold | 52.4% | **+3,202** | 胜率一般，但每笔改进大 |
| GBP | 50.8% | **-18,104** | 胜率 50%，但输的时候亏很多 |

**结论**：需要同时优化**胜率**和**每笔改进值**

### 3. 填充率是关键

| 资产 | 填充率 | 胜率 |
|------|-------|------|
| JPY | **71.0%** | **58.8%** ✅ |
| Nasdaq | 67.1% | 53.9% |
| EuroStoxx | 65.1% | 55.7% |
| Gold | 60.4% | 52.4% |
| German Bunds | 50.6% | 50.9% |
| GBP | **19.0%** | 50.8% |

**GBP 填充率仅 19%** - 说明 1 tick 限价单太激进！

---

## 📈 分方向表现

### Buy 方向

| 资产 | Buy 交易数 | Buy 胜率 |
|------|----------|---------|
| EuroStoxx | 112 | 33.0% |
| Nasdaq | 1,093 | 42.5% |
| Gold | 633 | 25.6% |
| German Bunds | 310 | 8.7% ❌ |

### Sell 方向

| 资产 | Sell 交易数 | Sell 胜率 |
|------|-----------|----------|
| German Bunds | 303 | **94.1%** ✅ |
| EuroStoxx | 100 | **81.0%** ✅ |
| GBP | 246 | **74.0%** ✅ |
| Gold | 643 | **78.7%** ✅ |
| JPY | 403 | 67.7% |
| Nasdaq | 1,071 | 65.6% |

**关键发现**：
- **Sell 方向普遍表现更好**（多数资产 >65%）
- **Buy 方向较弱**（多数 <50%）
- 说明 1 tick 限价单更适合卖单

---

## 💡 策略改进方向

### 当前策略问题

1. **固定 1 tick** - 不考虑资产差异
   - GBP 填充率仅 19%（tick size 太小）
   - German Bunds Buy 胜率仅 8.7%

2. **未区分买卖方向**
   - Sell 表现好 → 可以更激进（2 ticks）
   - Buy 表现差 → 需要更保守（0.5 ticks）

3. **未考虑波动率**
   - 高波动时 1 tick 容易被扫
   - 低波动时 1 tick 可能太保守

### 改进方案

**1. 资产特定参数**
```python
# 根据资产调整
tick_distances = {
    'GBP': 5,           # 5 ticks (填充率会提高)
    'German Bunds': 2,  # 2 ticks
    'JPY': 1,           # 1 tick (当前表现好)
    'Nasdaq': 1,
}
```

**2. 区分买卖方向**
```python
if direction == 'sell':
    distance = 2 * tick_size  # 激进
else:
    distance = 1 * tick_size  # 保守
```

**3. 动态调整**
```python
# 根据波动率调整
if ewmv > threshold:
    distance = 2 * tick_size  # 高波动，放宽
else:
    distance = 1 * tick_size  # 低波动，收紧
```

---

## 📊 生成的文件

| 文件 | 内容 |
|------|------|
| `simple_agent_comparison.py` | 对比脚本 |
| `results/simple_agent_comparison_summary.csv` | 详细数据 |
| `SIMPLE_AGENT_COMPARISON_REPORT.md` | 本报告 |

---

## 🎯 结论

### 总体表现

| 指标 | 数值 | 评价 |
|------|------|------|
| **总胜率** | **53.7%** | ✅ 跑赢 Agent 53.7% 的交易 |
| **总改进** | -15,444 ticks | ❌ 主要受 GBP 拖累 |
| **最佳资产** | JPY (58.8% 胜率，+370 ticks) | ✅ |
| **最差资产** | GBP (50.8% 胜率，-18K ticks) | ❌ |

### 关键洞察

1. **53.7% 胜率说明策略有竞争力**
   - 在 JPY/Gold/Bunds 上跑赢 Agent
   - 不是全面落后

2. **GBP 拖累整体表现**
   - 19% 填充率 → 需要调整 tick 距离
   - 虽然胜率 50.8%，但输的时候亏很多

3. **Sell 方向表现优于 Buy**
   - 多数资产 Sell 胜率 >65%
   - Buy 方向需要优化

### 下一步

1. **资产特定参数** - 不再用统一的 1 tick
2. **区分买卖方向** - Sell 可以更激进
3. **动态调整** - 根据波动率调整距离
4. **优化 Buy 方向** - 重点改进

---

**Generated**: 2026-04-17 | IEOR 4703 Term Project 2
