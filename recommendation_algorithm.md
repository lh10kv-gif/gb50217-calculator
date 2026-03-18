# 电缆型号推荐算法

## 一、算法流程

```
输入：运行参数、经济参数、技术约束、电缆可选范围
       ↓
步骤1：构建候选电缆集合
       - 根据电缆可选范围生成候选型号
       - 包括：材料(铜/铝)、绝缘(XLPE/PVC)、截面(标准系列)
       ↓
步骤2：计算经济截面
       - 对每个候选型号计算经济截面 S_ec
       - S_ec = I × √(90 × ρ × L × h × P_e / A)
       ↓
步骤3：选择标准截面
       - 对每个候选型号选择 ≥ S_ec 的最小标准截面
       ↓
步骤4：技术校核
       - 载流量校核：I_max ≥ I_load
       - 电压降校核：ΔU ≤ ΔU_max
       - 热稳定校核：S ≥ S_min(热稳定)
       - 不通过则增大截面重新校核
       ↓
步骤5：计算总拥有成本
       - TOC = CI + C_loss
       - CI: 电缆总成本（价格 × 长度）
       - C_loss: N年损耗成本
       ↓
步骤6：多目标优化（可选）
       - 综合评分 = w_eco × (1/TOC) + w_rel × 可靠性评分
       ↓
输出：最优电缆型号、技术参数、经济性分析、对比结果
```

## 二、详细步骤

### 步骤1：构建候选电缆集合

```python
def build_candidates(params):
    """
    构建候选电缆集合
    """
    candidates = []

    # 导体材料
    materials = params.get('materials', ['copper', 'aluminum'])

    # 绝缘类型
    insulations = params.get('insulations', ['XLPE', 'PVC'])

    # 电缆型号映射
    model_map = {
        ('copper', 'XLPE'): 'YJV',
        ('copper', 'PVC'): 'VV',
        ('aluminum', 'XLPE'): 'YJLV',
        ('aluminum', 'PVC'): 'VLV',
    }

    # 标准截面系列
    sections = params.get('sections', STANDARD_SECTIONS)

    # 生成组合
    for material in materials:
        for insulation in insulations:
            model = model_map.get((material, insulation))
            if model:
                for section in sections:
                    candidates.append({
                        'material': material,
                        'insulation': insulation,
                        'model': model,
                        'section': section,
                        'voltage': params.get('voltage', 10000)
                    })

    return candidates
```

### 步骤2：计算经济截面

```python
def calculate_economic_section(params, material):
    """
    计算经济截面
    S_ec = I × √(90 × ρ × L × h × P_e / A)
    """
    I = params['current']
    L = params['length']
    h = params['hours']
    P_e = params['price_electricity']

    # 电阻率
    rho = RHO_CU if material == 'copper' else RHO_AL

    # 可变成本系数 A
    # A = (CI_S1 - CI_S2) / (S1 - S2)
    # 简化：A = (导体单价 × 密度) / 1000
    price_per_kg = params['price_copper'] if material == 'copper' else params['price_aluminum']
    density = DENSITY_CU if material == 'copper' else DENSITY_AL
    A = (price_per_kg * density) / 1000  # 元/(m·mm²)

    # 经济截面
    S_ec = I * math.sqrt(90 * rho * L * h * P_e / A)

    return S_ec, A
```

### 步骤3：选择标准截面

```python
def select_standard_section(S_ec, sections):
    """
    选择大于等于 S_ec 的最小标准截面
    """
    for section in sorted(sections):
        if section >= S_ec:
            return section
    return sections[-1]  # 返回最大截面
```

### 步骤4：技术校核

```python
def check_technical_constraints(params, candidate):
    """
    技术校核
    返回：(是否通过, 详细信息)
    """
    info = {}

    # 4.1 载流量校核
    I_load = params['current']
    I_capacity = get_current_capacity(
        candidate['material'],
        candidate['section'],
        params.get('temperature', 40),
        params.get('installation_method', 'air')
    )
    info['current_capacity'] = {
        'required': I_load,
        'capacity': I_capacity,
        'passed': I_capacity >= I_load
    }

    # 4.2 电压降校核
    I_load = params['current']
    L = params['length']
    S = candidate['section']
    V = params['voltage']
    cos_phi = params.get('power_factor', 0.85)

    delta_U, delta_U_pct = calculate_voltage_drop(
        I_load, L, S, candidate['material'], V, cos_phi
    )

    info['voltage_drop'] = {
        'value': delta_U,
        'percent': delta_U_pct,
        'limit': params.get('voltage_drop_limit', 5.0),
        'passed': delta_U_pct <= params.get('voltage_drop_limit', 5.0)
    }

    # 4.3 热稳定校核
    I_sc = params.get('short_circuit_current', 25)
    t = params.get('short_circuit_duration', 0.2)

    thermal_passed = check_thermal_stability(
        S, candidate['material'], I_sc, t
    )

    info['thermal_stability'] = {
        'short_circuit_current': I_sc,
        'duration': t,
        'passed': thermal_passed
    }

    # 综合判断
    all_passed = all([
        info['current_capacity']['passed'],
        info['voltage_drop']['passed'],
        info['thermal_stability']['passed']
    ])

    return all_passed, info
```

### 步骤5：计算总拥有成本

```python
def calculate_toc(params, candidate):
    """
    计算总拥有成本（TOC）
    TOC = CI + C_loss
    """
    # 5.1 电缆成本 CI
    # 从价格表获取
    price_per_meter = get_cable_price(
        candidate['model'],
        candidate['section'],
        params['voltage']
    )
    CI = price_per_meter * params['length']

    # 5.2 N年损耗成本 C_loss
    I_load = params['current']
    L = params['length']
    S = candidate['section']
    h = params['hours']
    P_e = params['price_electricity']
    N = params.get('years', 30)

    # 单位长度电阻
    rho = RHO_CU if candidate['material'] == 'copper' else RHO_AL
    R = rho / S

    # 三相总损耗功率 (W)
    P_loss = 3 * I_load**2 * R * L

    # N年总损耗成本
    C_loss = (P_loss / 1000) * h * P_e * N

    # 总拥有成本
    TOC = CI + C_loss

    return {
        'cable_cost': CI,
        'loss_cost': C_loss,
        'total_cost': TOC,
        'loss_per_year': C_loss / N,
        'roi': calculate_roi(CI, C_loss)  # 投资回收期
    }
```

### 步骤6：多目标优化

```python
def optimize_candidates(candidates_with_scores, params):
    """
    多目标优化
    """
    w_eco = params.get('weight_economic', 1.0)
    w_rel = params.get('weight_reliability', 1.0)

    # 归一化评分
    # 经济性：成本越低分越高
    min_cost = min(c['toc']['total_cost'] for c in candidates_with_scores)
    max_cost = max(c['toc']['total_cost'] for c in candidates_with_scores)

    # 可靠性：裕度越大分越高
    for candidate in candidates_with_scores:
        # 经济性评分（0-1）
        cost = candidate['toc']['total_cost']
        candidate['scores']['economic'] = 1 - (cost - min_cost) / (max_cost - min_cost) if max_cost > min_cost else 1

        # 可靠性评分（0-1）
        tech = candidate['technical_checks']
        capacity_margin = tech['current_capacity']['capacity'] / tech['current_capacity']['required']
        voltage_drop_margin = tech['voltage_drop']['limit'] / tech['voltage_drop']['percent']

        candidate['scores']['reliability'] = min(
            capacity_margin - 1,
            voltage_drop_margin - 1
        ) / 5  # 归一化到0-1

        # 综合评分
        candidate['scores']['overall'] = (
            w_eco * candidate['scores']['economic'] +
            w_rel * candidate['scores']['reliability']
        ) / (w_eco + w_rel)

    # 按综合评分排序
    candidates_with_scores.sort(key=lambda x: x['scores']['overall'], reverse=True)

    return candidates_with_scores
```

## 三、输出格式

```python
{
    "best_candidate": {
        "model": "YJV-10-3×95",
        "material": "copper",
        "insulation": "XLPE",
        "section": 95,
        "voltage": 10000,
        "length": 100
    },
    "technical_checks": {
        "current_capacity": {...},
        "voltage_drop": {...},
        "thermal_stability": {...}
    },
    "economic_analysis": {
        "economic_section": 88.89,
        "selected_section": 95,
        "cable_cost": 15000,
        "loss_cost_per_year": 10888,
        "total_cost_30years": 266855,
        "roi": 2.5
    },
    "comparison": [
        {
            "model": "YJLV-10-3×150",
            "total_cost": 272025,
            "difference": 5170,
            "reason": "成本略高"
        }
    ],
    "reasoning": "铜芯YJV-10-3×95在满足技术约束的条件下，总拥有成本最低，因此推荐"
}
```
