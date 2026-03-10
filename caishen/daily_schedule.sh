#!/bin/bash
# 财神爷量化交易系统 - 每日定时任务
# 目标: 月收益 > 5%

WORKSPACE="/Users/roberto/Documents/OpenClawAgents"
LOG_DIR="$WORKSPACE/caishen/logs"
DATE=$(date +%Y%m%d)

mkdir -p $LOG_DIR

echo "========================================" >> $LOG_DIR/daily_$DATE.log
echo "💰 财神爷量化系统 - $(date '+%Y-%m-%d %H:%M:%S')" >> $LOG_DIR/daily_$DATE.log
echo "========================================" >> $LOG_DIR/daily_$DATE.log

# 获取当前时间
HOUR=$(date +%H)
MINUTE=$(date +%M)
TIME_VAL=$((10#$HOUR * 100 + 10#$MINUTE))

echo "当前时间: $HOUR:$MINUTE" >> $LOG_DIR/daily_$DATE.log

# 根据时间执行不同任务
case $TIME_VAL in
    930)
        echo "🌪️ 启动北风数据采集..." >> $LOG_DIR/daily_$DATE.log
        cd $WORKSPACE/beifeng && python3 beifeng.py >> $LOG_DIR/beifeng_$DATE.log 2>&1 &
        ;;
    1330)
        echo "🌸 启动东风盘中监控..." >> $LOG_DIR/daily_$DATE.log
        cd $WORKSPACE/dongfeng && python3 dongfeng.py --scan >> $LOG_DIR/dongfeng_$DATE.log 2>&1 &
        ;;
    1430)
        echo "🍃 更新西风热点..." >> $LOG_DIR/daily_$DATE.log
        cd $WORKSPACE/xifeng && python3 multi_source.py >> $LOG_DIR/xifeng_$DATE.log 2>&1 &
        ;;
    1445)
        echo "🀄 启动红中预警..." >> $LOG_DIR/daily_$DATE.log
        cd $WORKSPACE/hongzhong && python3 hongzhong.py --run >> $LOG_DIR/hongzhong_$DATE.log 2>&1 &
        ;;
    1450)
        echo "💰 启动发财买入..." >> $LOG_DIR/daily_$DATE.log
        cd $WORKSPACE/facai && python3 facai.py --buy >> $LOG_DIR/facai_$DATE.log 2>&1 &
        ;;
    1530)
        echo "🀆 启动白板归因分析..." >> $LOG_DIR/daily_$DATE.log
        cd $WORKSPACE/baiban && python3 baiban.py --daily >> $LOG_DIR/baiban_$DATE.log 2>&1 &
        ;;
    *)
        echo "⏳ 等待交易时段..." >> $LOG_DIR/daily_$DATE.log
        ;;
esac

echo "========================================" >> $LOG_DIR/daily_$DATE.log
