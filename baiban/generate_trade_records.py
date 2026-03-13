#!/usr/bin/env python3
"""
生成保守版15笔模拟操作记录
展示用户如何操作
"""

import random
from datetime import datetime, timedelta
from pathlib import Path

def generate_trade_records():
    """生成模拟交易记录"""
    
    strategies = {
        "趋势跟踪": {"win_rate": 0.85, "avg_return": 0.107, "holding": (7, 15)},
        "均值回归": {"win_rate": 0.80, "avg_return": 0.081, "holding": (2, 5)},
        "突破策略": {"win_rate": 0.85, "avg_return": 0.108, "holding": (3, 7)},
        "稳健增长": {"win_rate": 0.85, "avg_return": 0.084, "holding": (15, 30)},
        "热点追击": {"win_rate": 0.85, "avg_return": 0.131, "holding": (1, 3)}
    }
    
    all_records = []
    
    for strategy_name, config in strategies.items():
        print(f"\n{'='*70}")
        print(f"📊 {strategy_name} - 15笔模拟操作记录")
        print(f"{'='*70}")
        print(f"预期胜率: {config['win_rate']*100:.0f}%, 预期收益: {config['avg_return']*100:.1f}%")
        print(f"{'='*70}\n")
        
        records = []
        wins = 0
        
        for i in range(1, 16):
            # 模拟交易结果
            is_win = random.random() < config['win_rate']
            wins += 1 if is_win else 0
            
            # 生成股票代码
            stock_code = f"sh{random.randint(600000, 699999)}"
            
            # 入场价格
            entry_price = round(random.uniform(10, 100), 2)
            
            # 止损价 (-2%)
            stop_loss = round(entry_price * 0.98, 2)
            
            # 目标价
            target_1 = round(entry_price * 1.06, 2)
            target_2 = round(entry_price * 1.12, 2)
            target_3 = round(entry_price * 1.20, 2)
            
            # 持仓天数
            holding_days = random.randint(config['holding'][0], config['holding'][1])
            
            # 实际结果
            if is_win:
                # 盈利交易
                exit_level = random.choice([1, 2, 3])
                if exit_level == 1:
                    exit_price = target_1
                    exit_reason = "止盈目标1"
                    profit_pct = 6.0
                elif exit_level == 2:
                    exit_price = target_2
                    exit_reason = "止盈目标2"
                    profit_pct = 12.0
                else:
                    exit_price = target_3
                    exit_reason = "止盈目标3"
                    profit_pct = 20.0
            else:
                # 亏损交易
                exit_price = stop_loss
                exit_reason = "止损"
                profit_pct = -2.0
            
            # 生成日期
            entry_date = (datetime.now() - timedelta(days=random.randint(30, 90))).strftime('%Y-%m-%d')
            exit_date = (datetime.strptime(entry_date, '%Y-%m-%d') + timedelta(days=holding_days)).strftime('%Y-%m-%d')
            
            record = {
                'no': i,
                'stock_code': stock_code,
                'entry_date': entry_date,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'target_1': target_1,
                'target_2': target_2,
                'target_3': target_3,
                'exit_date': exit_date,
                'exit_price': exit_price,
                'profit_pct': profit_pct,
                'exit_reason': exit_reason,
                'holding_days': holding_days,
                'result': '✅ 盈利' if is_win else '❌ 亏损'
            }
            
            records.append(record)
            
            # 打印记录
            print(f"\n交易 #{i}")
            print(f"  股票: {stock_code}")
            print(f"  入场: {entry_date} @ ¥{entry_price}")
            print(f"  止损: ¥{stop_loss} (-2%)")
            print(f"  目标: ¥{target_1}(+6%) / ¥{target_2}(+12%) / ¥{target_3}(+20%)")
            print(f"  出场: {exit_date} @ ¥{exit_price} ({exit_reason})")
            print(f"  持仓: {holding_days}天")
            print(f"  结果: {record['result']} {profit_pct:+.2f}%")
        
        # 统计
        win_rate = wins / 15 * 100
        avg_profit = sum([r['profit_pct'] for r in records]) / 15
        
        print(f"\n{'='*70}")
        print(f"📈 {strategy_name} 统计")
        print(f"{'='*70}")
        print(f"  总交易: 15笔")
        print(f"  盈利: {wins}笔")
        print(f"  亏损: {15-wins}笔")
        print(f"  胜率: {win_rate:.1f}%")
        print(f"  平均收益: {avg_profit:.2f}%")
        print(f"{'='*70}")
        
        all_records.extend([(strategy_name, r) for r in records])
    
    return all_records


def generate_user_operation_log():
    """生成用户操作日志示例"""
    
    log = """
# 📝 用户操作日志示例

## 典型交易日操作流程

### 14:45 - 接收信号
```
Discord通知:
🀄 红中预警
策略: 趋势跟踪
股票: sh600348 (华阳股份)
入场价: 10.27
止损价: 10.06 (-2%)
目标1: 10.89 (+6%)
目标2: 11.50 (+12%)
建议仓位: 20%
```

### 14:48 - 确认信号
- ✅ 检查大盘: 上证指数ADX=32 (>20，符合)
- ✅ 检查板块: 煤炭板块热度高
- ✅ 检查个股: 趋势向上，成交量放大

### 14:52 - 下单入场
```
操作: 买入 sh600348
数量: 2000股 (约20%仓位)
价格: 市价10.27
金额: ¥20,540
```

### 14:55 - 设置止损
```
条件单:
股票: sh600348
条件: 价格跌至10.06
操作: 自动卖出2000股
```

### 持有期间 - 每日跟踪
- Day 1: 收盘价10.35 (+0.8%)，继续持仓
- Day 2: 收盘价10.58 (+3.0%)，移动止损至10.21
- Day 3: 收盘价11.13 (+8.4%)，触及目标1！

### Day 3 - 分批止盈
```
14:50操作:
1. 卖出600股 @ 11.13 (目标1，30%仓位)
   盈利: (11.13-10.27)*600 = ¥516

剩余1400股，继续持仓
```

### Day 5 - 继续止盈
```
收盘价11.76 (+14.5%)，触及目标2！

15:00操作:
2. 卖出800股 @ 11.76 (目标2，40%仓位)
   盈利: (11.76-10.27)*800 = ¥1,192

剩余600股，等待目标3
```

### Day 8 - 最终止盈
```
收盘价12.32 (+20%)，触及目标3！

14:45操作:
3. 卖出600股 @ 12.32 (目标3，剩余30%)
   盈利: (12.32-10.27)*600 = ¥1,230

总盈利: ¥516 + ¥1,192 + ¥1,230 = ¥2,938
收益率: 14.3%
```

---

## 止损示例

### 14:45 - 接收信号
```
策略: 突破策略
股票: sh301667
入场价: 25.50
止损价: 24.99 (-2%)
```

### 14:52 - 买入
```
买入400股 @ 25.50
金额: ¥10,200
```

### Day 2 - 触发止损
```
早盘低开，价格跌至24.80

09:35自动触发:
卖出400股 @ 24.99 (止损价)
亏损: (24.99-25.50)*400 = -¥204
收益率: -2.0%

严格执行止损，不补仓！
```

---

## 月度汇总示例

| 策略 | 交易数 | 盈利 | 亏损 | 胜率 | 总收益 |
|------|--------|------|------|------|--------|
| 趋势跟踪 | 3 | 3 | 0 | 100% | +28.5% |
| 均值回归 | 3 | 2 | 1 | 67% | +12.3% |
| 突破策略 | 3 | 3 | 0 | 100% | +24.6% |
| 稳健增长 | 3 | 2 | 1 | 67% | +11.8% |
| 热点追击 | 3 | 3 | 0 | 100% | +35.2% |
| **合计** | **15** | **13** | **2** | **87%** | **+112.4%** |

**注**: 以上为模拟示例，实际收益会有差异
"""
    return log


if __name__ == '__main__':
    print("="*70)
    print("🀆 白板 - 保守版15笔操作记录生成器")
    print("="*70)
    
    # 生成交易记录
    records = generate_trade_records()
    
    # 生成操作日志
    log = generate_user_operation_log()
    
    # 保存到文件
    log_file = Path(__file__).parent / "USER_OPERATION_LOG.md"
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(log)
    
    print(f"\n\n📄 用户操作日志已保存: {log_file}")
    print("="*70)
