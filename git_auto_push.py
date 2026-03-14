#!/usr/bin/env python3
"""
git_auto_push.py - Python 自动推送包装器
财神爷更新代码后自动调用此脚本推送到 GitHub
"""

import subprocess
import sys
from pathlib import Path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/ "utils"))
from agent_logger import get_logger

log = get_logger("System")


def auto_push():
    """自动推送代码到 GitHub"""
    repo_dir = Path.home() / "Documents/OpenClawAgents"
    
    # 检查仓库目录
    if not repo_dir.exists():
        log.info("❌ 错误: 仓库目录不存在")
        return False
    
    # 执行自动推送脚本
    script = repo_dir / "auto_push.sh"
    
    if not script.exists():
        log.info(f"❌ 错误: 推送脚本不存在 {script}")
        return False
    
    try:
        result = subprocess.run(
            ["bash", str(script)],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print(result.stdout)
        
        if result.returncode == 0:
            log.info("✅ 代码已自动推送到 GitHub")
            return True
        else:
            log.info(f"⚠️ 推送可能有问题:\n{result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log.info("❌ 推送超时")
        return False
    except Exception as e:
        log.info(f"❌ 推送失败: {e}")
        return False

if __name__ == "__main__":
    success = auto_push()
    sys.exit(0 if success else 1)
