#!/usr/bin/env python3
"""
统一通知模板系统 - Unified Notification System
支持多种通知类别，Discord富文本Embed格式
"""

import json
import requests
from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Dict, List, Optional, Any
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("通知系统")

class NotificationCategory(Enum):
    """通知类别"""
    ALERT = "alert"           # 紧急告警
    REPORT = "report"         # 状态报告
    TRADE = "trade"           # 交易信号
    MONITOR = "monitor"       # 监控信息
    SYSTEM = "system"         # 系统通知
    STRATEGY = "strategy"     # 策略更新

category_config = {
    NotificationCategory.ALERT: {
        "emoji": "🚨",
        "title": "紧急告警",
        "color": 0xFF0000,  # 红色
        "priority": 1
    },
    NotificationCategory.REPORT: {
        "emoji": "📊",
        "title": "状态报告",
        "color": 0x00FF00,  # 绿色
        "priority": 3
    },
    NotificationCategory.TRADE: {
        "emoji": "🀄",
        "title": "交易信号",
        "color": 0xFFD700,  # 金色
        "priority": 2
    },
    NotificationCategory.MONITOR: {
        "emoji": "💰",
        "title": "监控信息",
        "color": 0x00BFFF,  # 蓝色
        "priority": 4
    },
    NotificationCategory.SYSTEM: {
        "emoji": "⚙️",
        "title": "系统通知",
        "color": 0x808080,  # 灰色
        "priority": 5
    },
    NotificationCategory.STRATEGY: {
        "emoji": "🌬️",
        "title": "策略更新",
        "color": 0xFFA500,  # 橙色
        "priority": 3
    }
}


class UnifiedNotifier:
    """统一通知器"""
    
    def __init__(self, discord_webhook: str = None):
        self.discord_webhook = discord_webhook or "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"
    
    def send(self, 
             category: NotificationCategory,
             agent: str,
             message: str,
             fields: List[Dict[str, Any]] = None,
             footer: str = None,
             silent: bool = False) -> bool:
        """
        发送统一格式通知
        
        Args:
            category: 通知类别
            agent: Agent名称（如"北风","南风"）
            message: 主要消息内容
            fields: 附加字段列表 [{"name": "", "value": "", "inline": True}]
            footer: 页脚信息
            silent: 是否静默（仅告警类强制发送）
        
        Returns:
            是否发送成功
        """
        config = category_config[category]
        
        # 构建embed
        embed = self._build_embed(
            category=category,
            agent=agent,
            message=message,
            fields=fields,
            footer=footer,
            config=config
        )
        
        # 发送Discord
        return self._send_discord(embed, silent)
    
    def _build_embed(self, 
                     category: NotificationCategory,
                     agent: str,
                     message: str,
                     fields: List[Dict[str, Any]],
                     footer: str,
                     config: Dict) -> Dict:
        """构建Discord Embed"""
        
        embed = {
            "title": f"{config['emoji']} {config['title']} | {agent}",
            "description": message,
            "color": config['color'],
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": footer or f"财神爷量化交易系统 | 类别: {category.value}"
            }
        }
        
        if fields:
            embed["fields"] = fields
        
        return embed
    
    def _send_discord(self, embed: Dict, silent: bool = False) -> bool:
        """发送Discord Embed"""
        try:
            payload = {
                "embeds": [embed]
            }
            
            response = requests.post(
                self.discord_webhook,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 204:
                if not silent:
                    log.success(f"Discord通知已发送: {embed['title']}")
                return True
            else:
                log.fail(f"Discord发送失败: {response.status_code}")
                return False
                
        except Exception as e:
            log.fail(f"Discord异常: {e}")
            return False
    
    # 快捷方法
    def alert(self, agent: str, message: str, **kwargs):
        """发送告警"""
        return self.send(NotificationCategory.ALERT, agent, message, **kwargs)
    
    def report(self, agent: str, message: str, **kwargs):
        """发送报告"""
        return self.send(NotificationCategory.REPORT, agent, message, **kwargs)
    
    def trade(self, agent: str, message: str, **kwargs):
        """发送交易信号"""
        return self.send(NotificationCategory.TRADE, agent, message, **kwargs)
    
    def monitor(self, agent: str, message: str, **kwargs):
        """发送监控信息"""
        return self.send(NotificationCategory.MONITOR, agent, message, **kwargs)
    
    def system(self, agent: str, message: str, **kwargs):
        """发送系统通知"""
        return self.send(NotificationCategory.SYSTEM, agent, message, **kwargs)
    
    def strategy(self, agent: str, message: str, **kwargs):
        """发送策略更新"""
        return self.send(NotificationCategory.STRATEGY, agent, message, **kwargs)


# 全局通知器实例
_notifier = None

def get_notifier() -> UnifiedNotifier:
    """获取全局通知器实例"""
    global _notifier
    if _notifier is None:
        _notifier = UnifiedNotifier()
    return _notifier


# 快捷函数
def notify_alert(agent: str, message: str, **kwargs):
    """发送告警通知"""
    return get_notifier().alert(agent, message, **kwargs)

def notify_report(agent: str, message: str, **kwargs):
    """发送报告通知"""
    return get_notifier().report(agent, message, **kwargs)

def notify_trade(agent: str, message: str, **kwargs):
    """发送交易通知"""
    return get_notifier().trade(agent, message, **kwargs)

def notify_monitor(agent: str, message: str, **kwargs):
    """发送监控通知"""
    return get_notifier().monitor(agent, message, **kwargs)


if __name__ == '__main__':
    # 测试
    notifier = get_notifier()
    
    # 测试告警
    notifier.alert(
        agent="北风",
        message="数据库连接失败，请检查",
        fields=[
            {"name": "错误代码", "value": "ECONNREFUSED", "inline": True},
            {"name": "时间", "value": datetime.now().strftime('%H:%M:%S'), "inline": True}
        ]
    )
    
    # 测试报告
    notifier.report(
        agent="南风",
        message="今日策略运行完成",
        fields=[
            {"name": "信号数量", "value": "5个", "inline": True},
            {"name": "胜率", "value": "80%", "inline": True}
        ]
    )
    
    # 测试交易
    notifier.trade(
        agent="红中",
        message="发现交易机会",
        fields=[
            {"name": "股票", "value": "sh600348", "inline": True},
            {"name": "买入价", "value": "¥10.27", "inline": True}
        ]
    )
    
    print("\n✅ 通知系统测试完成！")
