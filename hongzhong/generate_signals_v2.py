#!/usr/bin/env python3
"""
红中信号生成器 - V2.0 (使用主数据库)
基于今日数据 + 南风策略，使用master_stocks获取准确股票名称
"""

import sqlite3
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("红中信号V2")

# 数据库路径
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
HONGZHONG_DB = Path.home() / "Documents/OpenClawAgents/hongzhong/data/signals_v3.db"

# 邮件配置
EMAIL_CONFIG = {
    "sender": "3823810468@qq.com",
    "password": "tmwhuqnthrpbcgec",
    "smtp_server": "smtp.qq.com",
    "smtp_port": 587,
    "receivers": ["3823810468@qq.com", "tensasky@gmail.com", "tensasky2003@gmail.com"]
}

class MasterDataService:
    """主数据服务 - 使用master_stocks表"""
    
    def __init__(self):
        self.db_path = BEIFENG_DB
    
    def get_stock_name(self, stock_code: str) -> str:
        """获取股票准确名称（使用master_stocks）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 先尝试精确匹配
        cursor.execute(
            "SELECT stock_name FROM master_stocks WHERE TRIM(stock_code) = ?",
            (stock_code,)
        )
        result = cursor.fetchone()
        
        if not result:
            # 尝试模糊匹配（处理换行符问题）
            cursor.execute(
                "SELECT stock_name FROM master_stocks WHERE stock_code LIKE ?",
                (f'%{stock_code}%',)
            )
            result = cursor.fetchone()
        
        conn.close()
        
        return result[0] if result else stock_code
    
    def get_stock_sector(self, stock_code: str) -> str:
        """获取股票所属板块"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT sector, industry FROM master_stocks WHERE TRIM(stock_code) = ?",
            (stock_code,)
        )
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            sector, industry = result
            return f"{sector}-{industry}" if industry else sector
        return "未知板块"

class NanfengStrategy:
    """南风策略评分系统"""
    
    def __init__(self):
        self.today = datetime.now().strftime('%Y-%m-%d')
        self.master_service = MasterDataService()
        
    def get_stock_data(self, stock_code: str) -> dict:
        """获取股票今日数据（含准确中文名）"""
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        
        # 今日数据
        cursor.execute(f"""
            SELECT open, high, low, close, volume, amount,
                   (close - open) / open * 100 as change_pct
            FROM daily
            WHERE stock_code = ? AND date(timestamp) = ?
        """, (stock_code, self.today))
        
        today_data = cursor.fetchone()
        
        if not today_data:
            conn.close()
            return None
        
        open_p, high, low, close, vol, amount, change = today_data
        
        # 从主数据库获取准确名称
        stock_name = self.master_service.get_stock_name(stock_code)
        sector = self.master_service.get_stock_sector(stock_code)
        
        # 近期数据
        cursor.execute("""
            SELECT close, volume
            FROM daily
            WHERE stock_code = ?
            ORDER BY timestamp DESC
            LIMIT 5
        """, (stock_code,))
        
        recent = cursor.fetchall()
        conn.close()
        
        return {
            'code': stock_code,
            'name': stock_name,
            'sector': sector,
            'open': open_p,
            'high': high,
            'low': low,
            'close': close,
            'volume': vol,
            'amount': amount,
            'change_pct': change,
            'recent_closes': [r[0] for r in recent],
            'recent_volumes': [r[1] for r in recent]
        }
    
    def calculate_score(self, data: dict) -> dict:
        """多因子评分"""
        if not data:
            return None
        
        score = 0
        details = {}
        
        # 1. 趋势评分 (40分)
        if len(data['recent_closes']) >= 5:
            ma5 = sum(data['recent_closes']) / len(data['recent_closes'])
            if data['close'] > ma5 * 1.05:
                trend_score = 40
                trend_comment = "强势上涨，突破均线"
            elif data['close'] > ma5:
                trend_score = 30
                trend_comment = "温和上涨"
            elif data['close'] > ma5 * 0.95:
                trend_score = 20
                trend_comment = "震荡整理"
            else:
                trend_score = 10
                trend_comment = "弱势下跌"
        else:
            trend_score = 20
            trend_comment = "数据不足"
        
        score += trend_score
        details['趋势'] = {'score': trend_score, 'comment': trend_comment}
        
        # 2. 动量评分 (30分)
        change = data['change_pct']
        if change > 9:
            momentum_score = 30
            momentum_comment = "涨停，强势"
        elif change > 5:
            momentum_score = 25
            momentum_comment = "大涨，积极"
        elif change > 2:
            momentum_score = 20
            momentum_comment = "上涨，关注"
        elif change > -2:
            momentum_score = 15
            momentum_comment = "震荡"
        elif change > -5:
            momentum_score = 10
            momentum_comment = "回调"
        else:
            momentum_score = 5
            momentum_comment = "大跌，回避"
        
        score += momentum_score
        details['动量'] = {'score': momentum_score, 'comment': momentum_comment}
        
        # 3. 成交量评分 (20分)
        if len(data['recent_volumes']) >= 2:
            avg_vol = sum(data['recent_volumes'][1:]) / len(data['recent_volumes'][1:])
            if avg_vol > 0:
                vol_ratio = data['volume'] / avg_vol
                if vol_ratio > 3:
                    vol_score = 20
                    vol_comment = "巨量，资金关注"
                elif vol_ratio > 2:
                    vol_score = 15
                    vol_comment = "放量，活跃"
                elif vol_ratio > 1:
                    vol_score = 10
                    vol_comment = "正常"
                else:
                    vol_score = 5
                    vol_comment = "缩量"
            else:
                vol_score = 10
                vol_comment = "数据不足"
        else:
            vol_score = 10
            vol_comment = "数据不足"
        
        score += vol_score
        details['成交量'] = {'score': vol_score, 'comment': vol_comment}
        
        # 4. 价格位置评分 (10分)
        if data['high'] > data['low']:
            price_position = (data['close'] - data['low']) / (data['high'] - data['low'])
            if price_position > 0.8:
                price_score = 10
                price_comment = "接近高点，强势"
            elif price_position > 0.5:
                price_score = 7
                price_comment = "中高位"
            else:
                price_score = 4
                price_comment = "低位"
        else:
            price_score = 5
            price_comment = "平盘"
        
        score += price_score
        details['价格位置'] = {'score': price_score, 'comment': price_comment}
        
        # 信号判断
        if score >= 80:
            signal = "强烈买入"
            signal_emoji = "🚀"
        elif score >= 65:
            signal = "买入"
            signal_emoji = "📈"
        elif score >= 50:
            signal = "关注"
            signal_emoji = "👀"
        elif score >= 35:
            signal = "观望"
            signal_emoji = "⏸️"
        else:
            signal = "回避"
            signal_emoji = "❌"
        
        return {
            'code': data['code'],
            'name': data['name'],
            'sector': data['sector'],
            'price': data['close'],
            'change': data['change_pct'],
            'score': score,
            'signal': signal,
            'signal_emoji': signal_emoji,
            'details': details,
            'ma5': sum(data['recent_closes']) / len(data['recent_closes']) if data['recent_closes'] else data['close'],
            'volume_ratio': data['volume'] / (sum(data['recent_volumes'][1:]) / len(data['recent_volumes'][1:])) if len(data['recent_volumes']) > 1 else 1
        }

class HongzhongSignal:
    """红中信号生成与发送"""
    
    def __init__(self):
        self.strategy = NanfengStrategy()
        self.signals = []
    
    def scan_all_stocks(self, limit: int = 100):
        """扫描所有股票生成信号"""
        log.step(f"开始扫描股票，生成交易信号")
        
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT stock_code
            FROM daily
            WHERE date(timestamp) = '{self.strategy.today}'
            ORDER BY (close - open) / open * 100 DESC
            LIMIT {limit}
        """)
        
        stocks = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        log.info(f"扫描 {len(stocks)} 只股票")
        
        for stock in stocks:
            data = self.strategy.get_stock_data(stock)
            if data:
                result = self.strategy.calculate_score(data)
                if result and result['score'] >= 65:
                    self.signals.append(result)
        
        self.signals.sort(key=lambda x: x['score'], reverse=True)
        
        log.success(f"生成 {len(self.signals)} 个交易信号")
        return self.signals
    
    def generate_email_content(self) -> str:
        """生成邮件内容（含准确股票名和板块）"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .header {{ background: #1a1a2e; color: white; padding: 20px; text-align: center; }}
                .signal {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
                .strong-buy {{ border-left: 5px solid #ff4444; }}
                .buy {{ border-left: 5px solid #ff8800; }}
                .stock-info {{ background: #f9f9f9; padding: 10px; margin: 10px 0; border-radius: 3px; }}
                .stock-name {{ font-size: 18px; font-weight: bold; color: #333; }}
                .stock-sector {{ color: #666; font-size: 14px; }}
                .score {{ font-size: 24px; font-weight: bold; color: #ff4444; }}
                .price {{ font-size: 20px; color: #333; }}
                .targets {{ background: #f5f5f5; padding: 10px; margin-top: 10px; border-radius: 3px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #f0f0f0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎯 红中交易信号报告 V2.0</h1>
                <p>生成时间: {now}</p>
                <p>数据来源: 北风实时采集 | 策略: 南风V5.1 | 名称来源: 主数据库</p>
            </div>
            
            <h2>📊 今日市场概况</h2>
            <ul>
                <li>分析股票数: 100只 (涨幅前列)</li>
                <li>生成信号数: {len(self.signals)}个</li>
                <li>策略版本: 保守版 (评分≥65)</li>
                <li>数据质量: ✅ 使用master_stocks主数据库</li>
            </ul>
            
            <h2>🚀 重点交易信号 (Top 10)</h2>
        """
        
        for i, signal in enumerate(self.signals[:10], 1):
            signal_class = "strong-buy" if signal['score'] >= 80 else "buy"
            
            html += f"""
            <div class="signal {signal_class}">
                <h3>{i}. {signal['signal_emoji']} {signal['code']} - {signal['signal']}</h3>
                
                <div class="stock-info">
                    <div class="stock-name">{signal['name']}</div>
                    <div class="stock-sector">所属板块: {signal['sector']}</div>
                </div>
                
                <div class="score">综合评分: {signal['score']}/100</div>
                <div class="price">当前价: ¥{signal['price']:.2f} (涨跌: {signal['change']:+.2f}%)</div>
                
                <h4>📈 评分详情:</h4>
                <table>
                    <tr><th>维度</th><th>得分</th><th>评价</th></tr>
            """
            
            for dimension, info in signal['details'].items():
                html += f"<tr><td>{dimension}</td><td>{info['score']}分</td><td>{info['comment']}</td></tr>"
            
            html += f"""
                </table>
                
                <div class="targets">
                    <strong>🎯 操作建议:</strong><br>
                    买入价: ¥{signal['price']:.2f}<br>
                    止损价: ¥{signal['price'] * 0.95:.2f} (-5%)<br>
                    目标价1: ¥{signal['price'] * 1.08:.2f} (+8%)<br>
                    目标价2: ¥{signal['price'] * 1.15:.2f} (+15%)
                </div>
            </div>
            """
        
        html += """
            <hr>
            <p><strong>⚠️ 风险提示:</strong></p>
            <ul>
                <li>以上信号基于技术分析生成，不构成投资建议</li>
                <li>股市有风险，投资需谨慎</li>
                <li>股票名称数据来自主数据库，每日更新</li>
                <li>建议单只股票仓位不超过20%</li>
            </ul>
            
            <p style="text-align: center; color: #666; margin-top: 30px;">
                本报告由 OpenClawAgents 系统自动生成<br>
                红中交易信号系统 V2.0 (使用Master Database)
            </p>
        </body>
        </html>
        """
        
        return html
    
    def send_email(self):
        """发送邮件"""
        try:
            log.step("正在发送邮件...")
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🎯 红中交易信号V2.0 - {datetime.now().strftime('%Y-%m-%d')} (含准确股票名)"
            msg['From'] = EMAIL_CONFIG['sender']
            
            receivers = EMAIL_CONFIG['receivers']
            msg['To'] = ', '.join(receivers)
            
            html_content = self.generate_email_content()
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
            server.starttls()
            server.login(EMAIL_CONFIG['sender'], EMAIL_CONFIG['password'])
            server.sendmail(EMAIL_CONFIG['sender'], receivers, msg.as_string())
            server.quit()
            
            log.success(f"✅ 邮件已发送至 {len(receivers)} 个邮箱")
            return True
            
        except Exception as e:
            log.error(f"❌ 邮件发送失败: {e}")
            return False

def main():
    """主程序"""
    print("="*70)
    print("🎯 红中信号生成器 V2.0 - 使用主数据库")
    print("="*70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("✅ 数据来源: master_stocks (已更新5,347只股票)")
    print()
    
    hongzhong = HongzhongSignal()
    
    # 扫描股票生成信号
    signals = hongzhong.scan_all_stocks(limit=100)
    
    if not signals:
        print("❌ 未生成有效信号")
        return
    
    # 显示信号
    print(f"\n📊 生成 {len(signals)} 个交易信号 (评分≥65):\n")
    for i, s in enumerate(signals[:10], 1):
        print(f"{i}. {s['signal_emoji']} {s['code']} {s['name']}")
        print(f"   板块: {s['sector']}")
        print(f"   信号: {s['signal']} (评分{s['score']}, ¥{s['price']:.2f})\n")
    
    # 发送邮件
    print("="*70)
    success = hongzhong.send_email()
    
    if success:
        print("\n✅ 信号生成和发送完成！")
        print(f"📧 请查收邮箱: {', '.join(EMAIL_CONFIG['receivers'])}")
        print("\n💡 本次更新:")
        print("   • 使用master_stocks主数据库")
        print("   • 股票名称更准确")
        print("   • 新增所属板块信息")
    else:
        print("\n⚠️ 邮件发送失败")
    
    print("="*70)

if __name__ == '__main__':
    main()
