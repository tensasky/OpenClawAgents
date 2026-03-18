# 📋 发布版本检查清单 (v4.8.0+)

**每次发布前必须逐项检查**

---

## 1. 版本号检查

- [ ] VERSION.md 版本号已更新
- [ ] README.md 版本号已更新
- [ ] CHANGELOG.md 已添加新版本记录

## 2. Agent版本检查

| Agent | 文件 | 版本 |
|-------|------|------|
| 北风 | beifeng/beifeng.py | V3.1 |
| 西风 | xifeng/xifeng_v2_sector.py | V2.0 |
| 东风 | dongfeng/dongfeng_v21.py | V2.1 |
| 南风 | nanfeng/nanfeng_v5_1.py | V5.5 |
| 红中 | hongzhong/generate_signals_multi.py | V3.5 |
| 发财 | facai/facai.py | V1.1 |
| 判官 | judge/data_validator.py | V1.2 |
| 白板 | baiban/baiban.py | V1.0 |
| 财神爷 | caishen/caishen.py | V5.2 |

**命令**:
```bash
grep -n "V[0-9]" beifeng/beifeng.py | head -1
grep -n "V[0-9]" xifeng/xifeng_v2_sector.py | head -1
grep -n "V[0-9]" dongfeng/dongfeng_v21.py | head -1
grep -n "V[0-9]" nanfeng/nanfeng_v5_1.py | head -1
grep -n "V[0-9]" hongzhong/generate_signals_multi.py | head -1
```

## 3. 文档检查

- [ ] README.md 时间戳已更新
- [ ] docs/BRD.md 版本同步
- [ ] docs/PRD.md 版本同步
- [ ] docs/SDD.md 版本同步
- [ ] docs/CODE_LOGIC.md 版本同步

## 4. 代码审查

- [ ] 无语法错误: `python3 -m py_compile *.py`
- [ ] 核心文件无遗漏

## 5. 清理检查

- [ ] 无过时文件残留 (检查archive/)
- [ ] 无调试代码
- [ ] 无敏感信息泄露

## 6. Git检查

- [ ] Git status 干净
- [ ] 已添加tag
- [ ] 已推送到origin

---

## 快速检查命令

```bash
# 检查所有Agent版本
echo "=== Agent版本 ===" && \
grep -h "^.*V[0-9]" beifeng/beifeng.py xifeng/xifeng_v2_sector.py dongfeng/dongfeng_v21.py nanfeng/nanfeng_v5_1.py hongzhong/generate_signals_multi.py facai/facai.py | head -5

# 检查README版本
grep "版本" README.md | head -2
```

---

*创建时间: 2026-03-18*
