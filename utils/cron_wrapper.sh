#!/bin/bash
# Cron脚本锁包装器 (Bash版本)
# 
# 使用方法:
#   source /path/to/utils/cron_wrapper.sh
#   with_lock "lock_name" 60 || exit 1
#   
#   # 你的脚本逻辑
#   ...
#   
# 锁会在脚本结束时自动释放

# 锁目录
LOCK_DIR="${HOME}/Documents/OpenClawAgents/.locks"

# 全局变量
_LOCK_FD=""
_LOCK_NAME=""

# 获取锁
acquire_lock() {
    local lock_name="$1"
    local timeout="${2:-30}"
    local lock_file="${LOCK_DIR}/${lock_name}.lock"
    
    # 创建锁目录
    mkdir -p "$LOCK_DIR"
    
    # 打开锁文件，使用自定义文件描述符
    exec 200>"$lock_file"
    _LOCK_FD=200
    
    if ! flock -w "$timeout" 200; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 获取锁 '$lock_name' 超时" >&2
        exec 200>&-
        return 1
    fi
    
    # 写入PID
    echo $$ >&200
    
    _LOCK_NAME="$lock_name"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 获取锁 '$lock_name' 成功 (PID: $$)"
    return 0
}

# 释放锁
release_lock() {
    local lock_name="${1:-$_LOCK_NAME}"
    
    if [ -n "$_LOCK_FD" ]; then
        flock -u $_LOCK_FD 2>/dev/null
        exec $_LOCK_FD>&- 2>/dev/null
        _LOCK_FD=""
    fi
    
    local lock_file="${LOCK_DIR}/${lock_name}.lock"
    rm -f "$lock_file" 2>/dev/null
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 释放锁 '$lock_name'"
    _LOCK_NAME=""
}

# 检查锁状态
check_lock_status() {
    local lock_name="$1"
    local lock_file="${LOCK_DIR}/${lock_name}.lock"
    
    if [ ! -f "$lock_file" ]; then
        echo "available"
        return 0
    fi
    
    # 尝试获取锁（非阻塞）
    if exec 201>"$lock_file" 2>/dev/null; then
        if flock -w 1 201; then
            flock -u 201 2>/dev/null
            exec 201>&- 2>/dev/null
            echo "available"
        else
            local pid=$(cat "$lock_file" 2>/dev/null)
            echo "locked (PID: $pid)"
        fi
    else
        echo "locked"
    fi
}

# 清理退出时的锁
_cleanup_lock() {
    if [ -n "$_LOCK_NAME" ]; then
        release_lock "$_LOCK_NAME"
    fi
}

# 便捷函数：获取锁并设置自动清理
# 使用: with_lock "lock_name" timeout
with_lock() {
    local lock_name="$1"
    local timeout="${2:-30}"
    
    acquire_lock "$lock_name" "$timeout"
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    # 设置退出时自动释放
    trap '_cleanup_lock' EXIT INT TERM
    
    return 0
}
