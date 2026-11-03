""" 自动调度器 ======================== 功能：让数据采集程序自动定时运行，你不用每次手动启动 使用方法： python scheduler.py 启动后它会一直在后台运行，按照 config.yaml 里设置的间隔自动采集数据。 即使你关了终端，它也会继续运行（如果用 nohup 启动的话）。 停止方法： 按 Ctrl+C 即可停止 """

import os
import sys
import time
import schedule
from datetime import datetime

# 导入采集程序的主函数
from collector import run_collection, load_config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def job():
    """定时执行的任务：运行一次数据采集"""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⏰ 定时任务触发")
    try:
        run_collection()
    except Exception as e:
        print(f"[ERROR] 采集失败: {e}")


def main():
    """主函数：设置定时任务并持续运行"""
    config = load_config()
    interval = config["automation"]["interval_minutes"]
    start_hour = config["automation"]["start_hour"]
    end_hour = config["automation"]["end_hour"]
    
    print("=" * 50)
    print("🤖 A股数据自动采集调度器")
    print("=" * 50)
    print(f" 采集间隔：每 {interval} 分钟")
    print(f" 运行时段：每天 {start_hour}:00 - {end_hour}:00")
    print(f" 按 Ctrl+C 停止")
    print("=" * 50)
    
    # 设置定时任务
    schedule.every(interval).minutes.do(job)
    
    # 启动时先运行一次
    print("\n🚀 首次启动，立即运行一次采集...")
    job()
    
    # 持续运行，检查是否到了执行时间
    while True:
        try:
            now = datetime.now()
            current_hour = now.hour
            
            # 只在指定时间段内运行
            if start_hour <= current_hour < end_hour:
                schedule.run_pending()
            else:
                # 非运行时段，每小时检查一次
                if now.minute == 0:
                    print(f" [{now.strftime('%H:%M')}] 当前不在运行时段，等待中...")
            
            time.sleep(30)  # 每30秒检查一次
            
        except KeyboardInterrupt:
            print("\n\n👋 调度器已停止")
            break
        except Exception as e:
            print(f"[ERROR] 调度器异常: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()
