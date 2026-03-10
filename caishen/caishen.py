#!/usr/bin/env python3
"""
财神爷 (Orchestrator) —— 编排智能体
任务编排、Agent调度、执行路径优化
"""

import json
import logging
import subprocess
import argparse
import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import schedule

# 配置路径
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
SKILLS_DIR = BASE_DIR / "skills"

# Agent 路径
AGENTS = {
    'beifeng': Path.home() / "Documents/OpenClawAgents/beifeng",
    'xifeng': Path.home() / "Documents/OpenClawAgents/xifeng",
    'nanfeng': Path.home() / "Documents/OpenClawAgents/nanfeng",
    'dongfeng': Path.home() / "Documents/OpenClawAgents/dongfeng",
    'hongzhong': Path.home() / "Documents/OpenClawAgents/hongzhong",
    'facai': Path.home() / "Documents/OpenClawAgents/facai",
    'baiban': Path.home() / "Documents/OpenClawAgents/baiban"
}

# 状态文件
WORKFLOW_STATE = DATA_DIR / "workflow_state.json"
AGENT_STATUS = DATA_DIR / "agent_status.json"
EXECUTION_LOG = DATA_DIR / "execution_log.json"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
SKILLS_DIR.mkdir(exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"caishen_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("财神爷")


class MarketState(Enum):
    """市场状态"""
    IDLE = "idle"
    PRE_MARKET = "pre_market"      # 盘前
    MORNING = "morning"            # 上午盘
    NOON_BREAK = "noon_break"      # 午休
    AFTERNOON = "afternoon"        # 下午盘
    PRE_CLOSE = "pre_close"        # 收盘前
    POST_MARKET = "post_market"    # 收盘后
    WEEKLY_REVIEW = "weekly_review" # 周末复盘


@dataclass
class AgentSkill:
    """Agent技能配置"""
    name: str
    version: str
    enabled: bool
    schedule: List[str]  # 定时触发时间
    dependencies: List[str]  # 依赖的其他Agent
    timeout: int  # 执行超时(秒)
    retry_count: int


@dataclass
class ExecutionRecord:
    """执行记录"""
    timestamp: str
    agent: str
    action: str
    status: str  # success/failed
    duration: float
    output: str


class AgentManager:
    """Agent管理器"""
    
    def __init__(self):
        self.skills = self._load_skills()
        self.status = self._load_status()
    
    def _load_skills(self) -> Dict[str, AgentSkill]:
        """加载Agent技能配置"""
        default_skills = {
            'beifeng': AgentSkill('北风', '2.0.0', True, ['09:15', '09:30', '13:00'], [], 300, 3),
            'xifeng': AgentSkill('西风', '1.0.0', True, ['14:30'], ['beifeng'], 60, 2),
            'nanfeng': AgentSkill('南风', '4.0.0', True, ['14:45'], ['beifeng'], 120, 2),
            'dongfeng': AgentSkill('东风', '1.0.0', True, ['13:30', '13:45', '14:00'], ['beifeng', 'xifeng'], 300, 2),
            'hongzhong': AgentSkill('红中', '1.0.0', True, ['14:45'], ['nanfeng', 'dongfeng'], 60, 3),
            'facai': AgentSkill('发财', '1.0.0', True, ['14:50'], ['hongzhong'], 600, 2),
            'baiban': AgentSkill('白板', '1.0.0', True, ['15:30', 'sun:20:00'], ['facai'], 1800, 2)
        }
        
        # 从文件加载（如果存在）
        for agent_id in default_skills:
            skill_file = SKILLS_DIR / f"{agent_id}_skill.json"
            if skill_file.exists():
                try:
                    with open(skill_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        default_skills[agent_id] = AgentSkill(**data)
                except Exception as e:
                    logger.error(f"加载 {agent_id} 技能失败: {e}")
        
        return default_skills
    
    def _load_status(self) -> Dict:
        """加载Agent状态"""
        if AGENT_STATUS.exists():
            try:
                with open(AGENT_STATUS, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {agent: {'last_run': None, 'status': 'unknown'} for agent in AGENTS}
    
    def save_skills(self):
        """保存技能配置"""
        for agent_id, skill in self.skills.items():
            skill_file = SKILLS_DIR / f"{agent_id}_skill.json"
            with open(skill_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(skill), f, ensure_ascii=False, indent=2)
    
    def save_status(self):
        """保存Agent状态"""
        with open(AGENT_STATUS, 'w', encoding='utf-8') as f:
            json.dump(self.status, f, ensure_ascii=False, indent=2)
    
    def check_agent_health(self, agent_id: str) -> bool:
        """检查Agent健康状态"""
        agent_dir = AGENTS.get(agent_id)
        if not agent_dir or not agent_dir.exists():
            logger.error(f"Agent {agent_id} 目录不存在")
            return False
        
        # 检查主程序是否存在
        main_file = agent_dir / f"{agent_id}.py"
        if not main_file.exists():
            # 尝试其他命名
            for alt_name in [f"{agent_id}_v4.py", f"{agent_id}_v3.py", "main.py"]:
                if (agent_dir / alt_name).exists():
                    return True
            logger.error(f"Agent {agent_id} 主程序不存在")
            return False
        
        return True
    
    def get_agent_script(self, agent_id: str) -> Optional[Path]:
        """获取Agent主程序路径"""
        agent_dir = AGENTS.get(agent_id)
        if not agent_dir:
            return None
        
        # 尝试各种可能的文件名
        candidates = [
            agent_dir / f"{agent_id}.py",
            agent_dir / f"{agent_id}_v4.py",
            agent_dir / f"{agent_id}_v3.py",
            agent_dir / "main.py"
        ]
        
        for candidate in candidates:
            if candidate.exists():
                return candidate
        
        return None


class WorkflowEngine:
    """工作流引擎"""
    
    def __init__(self):
        self.agent_manager = AgentManager()
        self.current_state = MarketState.IDLE
        self.execution_history = []
    
    def detect_market_state(self) -> MarketState:
        """检测当前市场状态"""
        now = datetime.now()
        weekday = now.weekday()  # 0=周一, 6=周日
        hour = now.hour
        minute = now.minute
        time_val = hour * 100 + minute
        
        # 周末
        if weekday >= 5:
            if weekday == 6 and time_val >= 2000:
                return MarketState.WEEKLY_REVIEW
            return MarketState.IDLE
        
        # 交易日
        if time_val < 915:
            return MarketState.PRE_MARKET
        elif 915 <= time_val < 1130:
            return MarketState.MORNING
        elif 1130 <= time_val < 1300:
            return MarketState.NOON_BREAK
        elif 1300 <= time_val < 1445:
            return MarketState.AFTERNOON
        elif 1445 <= time_val < 1500:
            return MarketState.PRE_CLOSE
        else:
            return MarketState.POST_MARKET
    
    def get_scheduled_agents(self, state: MarketState) -> List[str]:
        """根据市场状态获取应执行的Agent"""
        state_agents = {
            MarketState.PRE_MARKET: ['beifeng'],
            MarketState.MORNING: ['beifeng', 'dongfeng'],
            MarketState.AFTERNOON: ['beifeng', 'dongfeng'],
            MarketState.PRE_CLOSE: ['xifeng', 'nanfeng', 'hongzhong', 'facai'],
            MarketState.POST_MARKET: ['baiban'],
            MarketState.WEEKLY_REVIEW: ['baiban']
        }
        return state_agents.get(state, [])
    
    async def execute_agent(self, agent_id: str, action: str = "run") -> bool:
        """执行Agent"""
        skill = self.agent_manager.skills.get(agent_id)
        if not skill or not skill.enabled:
            logger.info(f"Agent {agent_id} 已禁用或不存在")
            return False
        
        # 检查健康状态
        if not self.agent_manager.check_agent_health(agent_id):
            logger.error(f"Agent {agent_id} 健康检查失败")
            return False
        
        script = self.agent_manager.get_agent_script(agent_id)
        if not script:
            logger.error(f"找不到 Agent {agent_id} 的执行脚本")
            return False
        
        logger.info(f"💰 调度执行: {skill.name} ({agent_id}) - {action}")
        
        start_time = time.time()
        
        try:
            # 构建命令
            cmd = ['python3', str(script)]
            if action == 'monitor' and agent_id in ['dongfeng', 'facai']:
                cmd.append('--monitor' if agent_id == 'dongfeng' else '--risk')
            elif action == 'buy' and agent_id == 'facai':
                cmd.append('--buy')
            
            # 执行
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(script.parent)
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=skill.timeout
                )
                
                duration = time.time() - start_time
                success = process.returncode == 0
                
                # 记录执行
                record = ExecutionRecord(
                    timestamp=datetime.now().isoformat(),
                    agent=agent_id,
                    action=action,
                    status='success' if success else 'failed',
                    duration=duration,
                    output=stdout.decode('utf-8', errors='ignore')[:500]
                )
                self._log_execution(record)
                
                # 更新状态
                self.agent_manager.status[agent_id] = {
                    'last_run': datetime.now().isoformat(),
                    'status': 'success' if success else 'failed',
                    'duration': duration
                }
                self.agent_manager.save_status()
                
                if success:
                    logger.info(f"✅ {skill.name} 执行成功 ({duration:.1f}s)")
                else:
                    logger.error(f"❌ {skill.name} 执行失败: {stderr.decode('utf-8', errors='ignore')[:200]}")
                
                return success
                
            except asyncio.TimeoutError:
                process.kill()
                logger.error(f"⏱️ {skill.name} 执行超时")
                return False
                
        except Exception as e:
            logger.error(f"❌ 执行 {agent_id} 出错: {e}")
            return False
    
    def _log_execution(self, record: ExecutionRecord):
        """记录执行日志"""
        self.execution_history.append(asdict(record))
        
        # 保存到文件
        logs = []
        if EXECUTION_LOG.exists():
            try:
                with open(EXECUTION_LOG, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except:
                pass
        
        logs.insert(0, asdict(record))
        logs = logs[:1000]  # 保留最近1000条
        
        with open(EXECUTION_LOG, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    
    async def run_workflow(self, state: MarketState):
        """运行工作流"""
        agents = self.get_scheduled_agents(state)
        
        if not agents:
            logger.debug(f"状态 {state.value} 无Agent需要执行")
            return
        
        logger.info(f"💰 执行工作流: {state.value} -> {agents}")
        
        # 按依赖顺序执行
        executed = set()
        
        for agent_id in agents:
            skill = self.agent_manager.skills.get(agent_id)
            if not skill:
                continue
            
            # 检查依赖是否已执行
            deps_satisfied = all(dep in executed for dep in skill.dependencies)
            if not deps_satisfied:
                logger.warning(f"{agent_id} 依赖未满足，跳过")
                continue
            
            # 执行
            success = await self.execute_agent(agent_id)
            
            if success:
                executed.add(agent_id)
            else:
                # 重试
                for retry in range(skill.retry_count):
                    logger.info(f"{agent_id} 重试 ({retry+1}/{skill.retry_count})")
                    await asyncio.sleep(1)
                    success = await self.execute_agent(agent_id)
                    if success:
                        executed.add(agent_id)
                        break
    
    def optimize_workflow(self):
        """优化工作流"""
        logger.info("💰 执行工作流优化...")
        
        # 分析执行历史
        if not self.execution_history:
            logger.info("无执行历史，跳过优化")
            return
        
        # 计算各Agent平均执行时间
        agent_stats = {}
        for record in self.execution_history:
            agent = record['agent']
            if agent not in agent_stats:
                agent_stats[agent] = {'count': 0, 'total_time': 0, 'failures': 0}
            
            agent_stats[agent]['count'] += 1
            agent_stats[agent]['total_time'] += record['duration']
            if record['status'] == 'failed':
                agent_stats[agent]['failures'] += 1
        
        # 生成优化建议
        optimizations = []
        for agent, stats in agent_stats.items():
            avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
            failure_rate = stats['failures'] / stats['count'] * 100 if stats['count'] > 0 else 0
            
            skill = self.agent_manager.skills.get(agent)
            if skill:
                # 调整超时
                if avg_time > skill.timeout * 0.8:
                    skill.timeout = int(avg_time * 1.2)
                    optimizations.append(f"{agent}: 超时调整为 {skill.timeout}s")
                
                # 调整重试次数
                if failure_rate > 20:
                    skill.retry_count = min(skill.retry_count + 1, 5)
                    optimizations.append(f"{agent}: 重试次数调整为 {skill.retry_count}")
        
        # 保存优化后的配置
        self.agent_manager.save_skills()
        
        logger.info(f"优化完成: {len(optimizations)} 项调整")
        for opt in optimizations:
            logger.info(f"  - {opt}")


class CaishenOrchestrator:
    """财神爷编排器"""
    
    def __init__(self):
        self.workflow = WorkflowEngine()
        self.running = False
    
    async def daemon_mode(self):
        """守护模式 - 持续监控并调度"""
        logger.info("=" * 60)
        logger.info("💰 财神爷编排器启动 (守护模式)")
        logger.info("=" * 60)
        
        self.running = True
        last_state = None
        
        while self.running:
            try:
                # 检测市场状态
                current_state = self.workflow.detect_market_state()
                
                if current_state != last_state:
                    logger.info(f"市场状态变化: {last_state} -> {current_state}")
                    await self.workflow.run_workflow(current_state)
                    last_state = current_state
                
                # 每分钟检查一次
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"守护模式出错: {e}")
                await asyncio.sleep(60)
        
        logger.info("💰 财神爷编排器停止")
    
    def trigger_workflow(self, workflow_name: str):
        """手动触发工作流"""
        state_map = {
            'morning': MarketState.MORNING,
            'afternoon': MarketState.AFTERNOON,
            'preclose': MarketState.PRE_CLOSE,
            'postclose': MarketState.POST_MARKET,
            'weekly': MarketState.WEEKLY_REVIEW
        }
        
        state = state_map.get(workflow_name)
        if state:
            asyncio.run(self.workflow.run_workflow(state))
        else:
            logger.error(f"未知工作流: {workflow_name}")
    
    def show_status(self):
        """显示所有Agent状态"""
        print("\n" + "=" * 60)
        print("💰 财神爷·Agent状态监控")
        print("=" * 60)
        
        for agent_id, skill in self.workflow.agent_manager.skills.items():
            status = self.workflow.agent_manager.status.get(agent_id, {})
            health = "✅" if self.workflow.agent_manager.check_agent_health(agent_id) else "❌"
            enabled = "🟢" if skill.enabled else "⚪"
            
            print(f"\n{enabled} {health} {skill.name} ({agent_id})")
            print(f"   版本: {skill.version}")
            print(f"   定时: {', '.join(skill.schedule)}")
            print(f"   依赖: {', '.join(skill.dependencies) or '无'}")
            print(f"   上次运行: {status.get('last_run', '从未')}")
            print(f"   状态: {status.get('status', 'unknown')}")
        
        print("\n" + "=" * 60)
        print(f"当前市场状态: {self.workflow.detect_market_state().value}")
        print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description='财神爷 - 编排智能体')
    parser.add_argument('--daemon', action='store_true', help='守护模式（持续运行）')
    parser.add_argument('--trigger', type=str, help='手动触发工作流 (morning/afternoon/preclose/postclose/weekly)')
    parser.add_argument('--status', action='store_true', help='查看Agent状态')
    parser.add_argument('--optimize', action='store_true', help='执行工作流优化')
    parser.add_argument('--logs', action='store_true', help='查看执行日志')
    
    args = parser.parse_args()
    
    caishen = CaishenOrchestrator()
    
    if args.daemon:
        asyncio.run(caishen.daemon_mode())
    elif args.trigger:
        caishen.trigger_workflow(args.trigger)
    elif args.status:
        caishen.show_status()
    elif args.optimize:
        caishen.workflow.optimize_workflow()
    elif args.logs:
        if EXECUTION_LOG.exists():
            with open(EXECUTION_LOG, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            print(f"\n💰 最近10条执行记录:\n")
            for log in logs[:10]:
                print(f"  {log['timestamp'][:19]} | {log['agent']:<10} | {log['action']:<8} | {log['status']:<7} | {log['duration']:.1f}s")
            print()
        else:
            print("暂无执行日志")
    else:
        # 默认显示状态
        caishen.show_status()


if __name__ == "__main__":
    main()
