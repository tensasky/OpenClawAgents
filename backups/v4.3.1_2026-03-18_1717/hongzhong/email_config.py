# 邮件配置 - 请设置环境变量
# export SMTP_PASSWORD="your_password"

SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
SENDER_EMAIL = "3823810468@qq.com"
RECEIVER_EMAIL = "3823810468@qq.com"

# 从环境变量读取密码，如果没有则使用默认值（仅用于测试）
import os
SENDER_PASSWORD = os.getenv("SMTP_PASSWORD", "请设置环境变量SMTP_PASSWORD")
