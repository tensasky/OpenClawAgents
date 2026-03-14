#!/usr/bin/env python3
"""
统一日志配置 - 所有Agent共享
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

# 日志格式
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def setup_logger(name: str, log_file: Path = None, level=logging.INFO) -> logging.Logger:
    """
    设置统一格式的日志
    
    Args:
        name: logger名称（如 '北风', '南风'）
        log_file: 日志文件路径，None则只输出到控制台
        level: 日志级别
    
    Returns:
        配置好的logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 清除已有handler
    logger.handlers = []
    
    # 创建formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件输出（如果指定）
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


class AgentLogger:
    """Agent日志类 - 每个Agent实例化使用"""
    
    def __init__(self, agent_name: str, log_dir: Path = None):
        self.agent_name = agent_name
        self.log_dir = log_dir or Path.home() / ".openclaw/workspace/logs"
        self.log_file = self.log_dir / f"{agent_name.lower()}_{datetime.now().strftime('%Y%m%d')}.log"
        self.logger = setup_logger(agent_name, self.log_file)
    
    def info(self, msg: str):
        self.logger.info(msg)
    
    def warning(self, msg: str):
        self.logger.warning(msg)
    
    def error(self, msg: str):
        self.logger.error(msg)
    
    def debug(self, msg: str):
        self.logger.debug(msg)
    
    def success(self, msg: str):
        """成功信息 - 绿色高亮"""
        self.logger.info(f"✅ {msg}")
    
    def fail(self, msg: str):
        """失败信息 - 红色高亮"""
        self.logger.error(f"❌ {msg}")
    
    def step(self, step_name: str):
        """步骤开始"""
        self.logger.info(f"▶️  {step_name}")
    
    def complete(self, msg: str = "完成"):
        """步骤完成"""
        self.logger.info(f"✓ {msg}")


# 快捷函数
def get_logger(agent_name: str) -> AgentLogger:
    """获取Agent日志实例"""
    return AgentLogger(agent_name)


if __name__ == '__main__':
    # 测试
    log = get_logger("测试")
    log.info("普通信息")
    log.success("成功信息")
    log.fail("失败信息")
    log.step("执行步骤")
    log.warning("警告信息")
    log.complete("任务完成")
