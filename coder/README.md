# 码农 (Coder) - 代码开发 Agent

## 功能
- 代码生成
- 代码审查
- 重构建议
- 技术方案设计

## 目录结构
```
coder/
├── coder.py            # 主程序
├── templates/          # 代码模板
├── rules/              # 审查规则
└── README.md           # 本文件
```

## 使用
```bash
# 代码审查
python3 coder.py review <file.py>

# 生成代码
python3 coder.py generate "实现一个HTTP服务器"

# 重构建议
python3 coder.py refactor <file.py>
```

## 权限
- ✅ 可以读取代码
- ✅ 可以生成代码
- ✅ 可以写代码文件
- ❌ 禁止删除文件
- ❌ 部署需人工确认

## Emoji
👨‍💻
