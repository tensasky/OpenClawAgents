#!/usr/bin/env python3
"""
全面架构审查 - 财神爷主导
清理旧版本遗留数据，确保系统正确
"""

import os
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime

class FullSystemReview:
    """全面系统审查"""
    
    def __init__(self):
        self.base_path = Path.home() / "Documents/OpenClawAgents"
        self.issues = []
        self.fixed = []
        
    def run_full_review(self):
        """运行全面审查"""
        print("="*80)
        print("💰 财神爷 - 全面架构和代码审查")
        print("="*80)
        print(f"审查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 1. 数据库架构审查
        self.review_databases()
        
        # 2. 代码一致性审查
        self.review_code()
        
        # 3. 数据清理
        self.cleanup_data()
        
        # 4. 验证修复
        self.verify_fixes()
        
        # 输出报告
        self.print_report()
    
    def review_databases(self):
        """审查数据库架构"""
        print("\n" + "="*80)
        print("🗄️ 数据库架构审查")
        print("="*80)
        
        beifeng_db = self.base_path / "beifeng/data/stocks_real.db"
        
        if beifeng_db.exists():
            conn = sqlite3.connect(beifeng_db)
            cursor = conn.cursor()
            
            # 检查表结构
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t[0] for t in cursor.fetchall()]
            print(f"\n📊 北风数据库表: {tables}")
            
            # 检查是否有旧表残留
            if 'kline_data' in tables:
                self.issues.append("北风: 残留旧表kline_data")
                print("❌ 发现残留旧表: kline_data")
                
                # 清理旧表
                cursor.execute("DROP TABLE IF EXISTS kline_data")
                conn.commit()
                self.fixed.append("北风: 删除残留表kline_data")
                print("✅ 已删除旧表")
            
            # 检查数据一致性
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute(f"""
                SELECT COUNT(*) FROM daily
                WHERE date(timestamp) = '{today}'
            """)
            daily_count = cursor.fetchone()[0]
            
            cursor.execute(f"""
                SELECT COUNT(DISTINCT stock_code) FROM minute
                WHERE date(timestamp) = '{today}'
            """)
            minute_stocks = cursor.fetchone()[0]
            
            print(f"\n📈 今日数据:")
            print(f"  日线记录: {daily_count}")
            print(f"  分钟股票: {minute_stocks}")
            
            if daily_count != minute_stocks:
                self.issues.append(f"北风: 日线({daily_count})≠分钟({minute_stocks})")
                print(f"⚠️  数据不一致!")
            
            conn.close()
        
        # 检查旧数据库
        old_db = self.base_path / "beifeng/data/stocks.db"
        if old_db.exists():
            size_mb = old_db.stat().st_size / 1024 / 1024
            self.issues.append(f"北风: 旧数据库仍存在({size_mb:.1f}MB)")
            print(f"\n⚠️  旧数据库仍存在: {size_mb:.1f}MB")
            print("   建议: 已备份，可以删除")
    
    def review_code(self):
        """审查代码一致性"""
        print("\n" + "="*80)
        print("📜 代码一致性审查")
        print("="*80)
        
        # 检查所有Python文件
        py_files = list(self.base_path.rglob("*.py"))
        
        old_db_refs = []
        for py_file in py_files:
            if '.git' in str(py_file):
                continue
            try:
                content = py_file.read_text()
                if 'stocks.db' in content and 'stocks_real.db' not in content:
                    old_db_refs.append(py_file.relative_to(self.base_path))
            except:
                pass
        
        if old_db_refs:
            print(f"\n❌ 发现 {len(old_db_refs)} 个文件引用旧数据库:")
            for f in old_db_refs[:10]:
                print(f"  - {f}")
            if len(old_db_refs) > 10:
                print(f"  ... 还有 {len(old_db_refs)-10} 个")
            
            self.issues.append(f"代码: {len(old_db_refs)}个文件引用旧数据库")
        else:
            print("\n✅ 所有代码使用新数据库")
    
    def cleanup_data(self):
        """清理数据"""
        print("\n" + "="*80)
        print("🧹 数据清理")
        print("="*80)
        
        # 清理红中旧信号
        hongzhong_db = self.base_path / "hongzhong/data/signals_v3.db"
        if hongzhong_db.exists():
            conn = sqlite3.connect(hongzhong_db)
            cursor = conn.cursor()
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            # 检查重复信号
            cursor.execute(f"""
                SELECT stock_code, COUNT(*) as cnt
                FROM signals
                WHERE date(timestamp) = '{today}'
                GROUP BY stock_code
                HAVING cnt > 1
            """)
            
            duplicates = cursor.fetchall()
            if duplicates:
                print(f"\n🗑️  清理重复信号:")
                for code, cnt in duplicates:
                    print(f"  {code}: {cnt}个重复")
                    
                    # 保留最新的，删除旧的
                    cursor.execute(f"""
                        DELETE FROM signals
                        WHERE id IN (
                            SELECT id FROM signals
                            WHERE stock_code = '{code}'
                            AND date(timestamp) = '{today}'
                            ORDER BY timestamp ASC
                            LIMIT {cnt-1}
                        )
                    """)
                    self.fixed.append(f"红中: 清理{code}的{cnt-1}个重复信号")
                
                conn.commit()
                print(f"✅ 已清理重复信号")
            else:
                print("\n✅ 无重复信号")
            
            conn.close()
    
    def verify_fixes(self):
        """验证修复"""
        print("\n" + "="*80)
        print("✅ 修复验证")
        print("="*80)
        
        # 验证纳百川价格
        beifeng_db = self.base_path / "beifeng/data/stocks_real.db"
        conn = sqlite3.connect(beifeng_db)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute(f"""
            SELECT close FROM daily
            WHERE stock_code = 'sz301667'
            AND date(timestamp) = '{today}'
        """)
        
        result = cursor.fetchone()
        if result:
            price = result[0]
            if abs(price - 84.79) < 0.01:
                print(f"✅ 纳百川价格正确: ¥{price:.2f}")
            else:
                print(f"❌ 纳百川价格错误: ¥{price:.2f} (应为¥84.79)")
                self.issues.append(f"数据: 纳百川价格错误¥{price:.2f}")
        
        conn.close()
    
    def print_report(self):
        """输出报告"""
        print("\n" + "="*80)
        print("📊 审查报告")
        print("="*80)
        
        print(f"\n🔴 发现问题: {len(self.issues)} 个")
        for issue in self.issues:
            print(f"  ❌ {issue}")
        
        print(f"\n✅ 已修复: {len(self.fixed)} 个")
        for fix in self.fixed:
            print(f"  ✅ {fix}")
        
        print("\n" + "="*80)
        if self.issues:
            print("⚠️  仍有未解决问题")
        else:
            print("✅ 系统审查通过")
        print("="*80)


if __name__ == '__main__':
    reviewer = FullSystemReview()
    reviewer.run_full_review()
