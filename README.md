# GB50217 电缆经济选型计算器 V5

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

> 基于 GB 50217-2018《电力工程电缆设计标准》附录 B，实现电力电缆经济电流截面的自动计算与选型推荐

## 🎯 项目特点

- ✅ **经济电流密度公式化计算** - 按 GB50217 附录 B 公式动态计算，无需查表
- ✅ **全生命周期成本分析** - 综合考虑初始投资、运行损耗、运维费用
- ✅ **多因素技术校核** - 热稳定、载流量、电压降三项校验
- ✅ **支持铜芯/铝芯** - YJY22/YJLHY22 系列
- ✅ **支持 1kV/10kV** - 低压、中压配电

## 📦 安装

```bash
# 克隆仓库
git clone https://github.com/your-username/gb50217-calculator.git
cd gb50217-calculator

# 安装依赖（可选，仅 GUI 需要）
pip install -r requirements.txt
```

## 🚀 快速开始

### 命令行模式

```bash
# 基本用法
python calculate.py --current=200 --hours=5000 --material=copper --length=100

# 完整参数
python calculate.py \
  --current=200 \
  --hours=5000 \
  --material=copper \
  --length=100 \
  --voltage=10000 \
  --json

# 查看帮助
python calculate.py --help
```

### GUI 模式

```bash
pip install PyQt5
python calculate.py
```

## 📋 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|------|:----:|--------|------|
| `--current` | ✅ | - | 负荷电流 (A) |
| `--hours` | ✅ | - | 年最大负荷利用小时数 (h) |
| `--material` | ✅ | - | 导体材料 (copper/aluminum) |
| `--length` | ❌ | 100 | 电缆长度 (m) |
| `--voltage` | ❌ | 10000 | 电压等级 (V) |
| `--short_circuit` | ❌ | 25 | 短路电流 (kA) |
| `--power_factor` | ❌ | 0.85 | 功率因数 |
| `--json` | ❌ | - | 输出 JSON 格式 |

## 📚 文档

- [详细说明书](cable_calculator_v5_说明书.md) - 完整的功能介绍和使用指南
- [推荐算法](recommendation_algorithm.md) - 技术原理和算法详解
- [技能描述](SKILL.md) - OpenClaw 技能集成说明

## 🔬 核心算法

### 经济电流密度公式

```
Jec = √(1000 × a / (3 × ρ × τ × C2 × N))
```

| 参数 | 含义 |
|------|------|
| a | 电缆成本系数 (元/mm²·m) |
| ρ | 导体电阻率 (Ω·mm²/m) |
| τ | 最大损耗小时数 (h) |
| C2 | 电价 (元/kWh) |
| N | 年金现值系数 |

### 验证结果

经济截面与 LCC 最优截面 **完全一致**（差异 0 档）！

## 📜 引用标准

1. GB 50217-2018《电力工程电缆设计标准》
2. GB 50054-2011《低压配电设计规范》
3. 《工业与民用配电设计手册》第四版

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

[MIT License](LICENSE)

---

**让电缆选型更科学、更经济！** 🔌⚡
