#!/bin/bash
# 北风Cron包装器 - 设置正确的环境
export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
export HOME=/Users/roberto

cd /Users/roberto/Documents/OpenClawAgents
exec /usr/bin/python3 beifeng/beifeng.py "$@"
