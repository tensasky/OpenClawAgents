#!/usr/bin/env python3
"""
单元测试框架 - Unit Testing Framework
为Agent提供基础测试能力
"""

import unittest
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("单元测试")


class AgentTestCase(unittest.TestCase):
    """Agent测试基类"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        log.info(f"开始测试: {cls.__name__}")
        cls.test_results = []
    
    @classmethod
    def tearDownClass(cls):
        """测试类结束"""
        log.info(f"测试完成: {cls.__name__}")
        # 保存测试结果
        if cls.test_results:
            cls.save_test_results()
    
    @classmethod
    def save_test_results(cls):
        """保存测试结果"""
        result_dir = Path.home() / ".openclaw/workspace/test_results"
        result_dir.mkdir(parents=True, exist_ok=True)
        
        filename = result_dir / f"test_{cls.__name__}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(cls.test_results, f, ensure_ascii=False, indent=2)
        
        log.info(f"测试结果已保存: {filename}")
    
    def log_test(self, test_name: str, result: bool, message: str = ""):
        """记录测试结果"""
        status = "✅ 通过" if result else "❌ 失败"
        log.info(f"{status}: {test_name} - {message}")
        
        self.test_results.append({
            "test": test_name,
            "result": result,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })


class DatabaseTests(AgentTestCase):
    """数据库测试"""
    
    def test_database_connection(self):
        """测试数据库连接"""
        import sqlite3
        from pathlib import Path
        
        db_path = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            self.log_test("数据库连接", True, "连接成功")
            self.assertTrue(True)
        except Exception as e:
            self.log_test("数据库连接", False, str(e))
            self.fail(f"数据库连接失败: {e}")
    
    def test_daily_table_exists(self):
        """测试daily表存在"""
        import sqlite3
        from pathlib import Path
        
        db_path = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily'")
            result = cursor.fetchone()
            conn.close()
            
            if result:
                self.log_test("daily表存在", True)
                self.assertTrue(True)
            else:
                self.log_test("daily表存在", False, "表不存在")
                self.fail("daily表不存在")
        except Exception as e:
            self.log_test("daily表存在", False, str(e))
            self.fail(f"检查失败: {e}")


class AgentConfigTests(AgentTestCase):
    """Agent配置测试"""
    
    def test_agent_files_exist(self):
        """测试Agent文件存在"""
        agents = [
            ("北风", "beifeng/beifeng.py"),
            ("南风", "nanfeng/nanfeng_v5_1.py"),
            ("红中", "hongzhong/hongzhong_v33.py"),
            ("西风", "xifeng/xifeng_v2_sector.py"),
            ("东风", "dongfeng/dongfeng_v2.py"),
            ("发财", "facai/facai_v2.py"),
            ("白板", "baiban/baiban.py"),
            ("判官", "judge/judge_agent.py"),
        ]
        
        base_path = Path.home() / "Documents/OpenClawAgents"
        
        for agent_name, file_path in agents:
            full_path = base_path / file_path
            exists = full_path.exists()
            self.log_test(f"{agent_name}文件存在", exists, str(file_path))
            self.assertTrue(exists, f"{agent_name}文件不存在: {file_path}")


class UtilsTests(AgentTestCase):
    """工具类测试"""
    
    def test_logger(self):
        """测试日志模块"""
        try:
            from agent_logger import get_logger
            log = get_logger("测试")
            log.info("测试消息")
            self.log_test("日志模块", True)
            self.assertTrue(True)
        except Exception as e:
            self.log_test("日志模块", False, str(e))
            self.fail(f"日志模块失败: {e}")
    
    def test_notifier(self):
        """测试通知模块"""
        try:
            from unified_notifier import get_notifier, NotificationCategory
            notifier = get_notifier()
            self.assertIsNotNone(notifier)
            self.log_test("通知模块", True)
        except Exception as e:
            self.log_test("通知模块", False, str(e))
            self.fail(f"通知模块失败: {e}")
    
    def test_db_pool(self):
        """测试连接池"""
        try:
            from db_pool import get_pool, close_all_pools
            from pathlib import Path
            
            test_db = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
            if test_db.exists():
                pool = get_pool(test_db)
                stats = pool.get_stats()
                self.assertIsNotNone(stats)
                self.log_test("连接池", True, f"连接数: {stats['active_connections']}")
            else:
                self.log_test("连接池", True, "测试数据库不存在，跳过")
            
            close_all_pools()
        except Exception as e:
            self.log_test("连接池", False, str(e))


def run_all_tests():
    """运行所有测试"""
    log.step("开始运行单元测试")
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(DatabaseTests))
    suite.addTests(loader.loadTestsFromTestCase(AgentConfigTests))
    suite.addTests(loader.loadTestsFromTestCase(UtilsTests))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出总结
    print("\n" + "="*70)
    print("📊 测试总结")
    print("="*70)
    print(f"运行测试: {result.testsRun}")
    print(f"通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
