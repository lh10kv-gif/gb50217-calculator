#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电缆型号推荐系统
基于GB50217标准，推荐最优电缆型号
"""

import json
import sys
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict


# ============ 常数定义 ============

# 电阻率 (Ω·mm²/m)
# GB50217标准值: 铜 17.24×10^-9 Ω·m²/m = 0.01724 Ω·mm²/m
#                 铝 28.26×10^-9 Ω·m²/m = 0.02826 Ω·mm²/m
RHO_CU = 0.01724
RHO_AL = 0.02826

# 密度 (kg/m³)
DENSITY_CU = 8960
DENSITY_AL = 2700

# 标准截面系列 (mm²)
STANDARD_SECTIONS = [
    1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300, 400, 500
]

# 热稳定系数 K
K_CU = 143  # 铜芯
K_AL = 95   # 铝芯

# 默认电缆价格（元/m，参考价）
DEFAULT_CABLE_PRICES = {
    # YJV (铜芯交联)
    'YJV': {
        1.5: 8, 2.5: 10, 4: 15, 6: 20, 10: 30, 16: 45, 25: 65,
        35: 90, 50: 120, 70: 165, 95: 220, 120: 280, 150: 350,
        185: 430, 240: 550, 300: 700, 400: 900
    },
    # VV (铜芯聚氯乙烯)
    'VV': {
        1.5: 7, 2.5: 9, 4: 13, 6: 18, 10: 25, 16: 40, 25: 58,
        35: 80, 50: 108, 70: 150, 95: 200, 120: 255, 150: 320,
        185: 390, 240: 500, 300: 640, 400: 820, 500: 1000
    },
    # YJLV (铝芯交联)
    'YJLV': {
        1.5: 5, 2.5: 6, 4: 8, 6: 10, 10: 15, 16: 22, 25: 30,
        35: 40, 50: 52, 70: 70, 95: 90, 120: 110, 150: 135,
        185: 165, 240: 210, 300: 270, 400: 350, 500: 430
    },
    # VLV (铝芯聚氯乙烯)
    'VLV': {
        1.5: 4, 2.5: 5, 4: 7, 6: 9, 10: 13, 16: 20, 25: 28,
        35: 36, 50: 48, 70: 65, 95: 82, 120: 100, 150: 125,
        185: 150, 240: 195, 300: 250, 400: 320
    }
}

# 载流量修正系数（空气中，40℃）
CURRENT_CORRECTION_40C = {
    'XLPE': 0.87,
    'PVC': 0.82
}

# 基准载流量（空气中，30℃，A）
BASE_CURRENT_CAPACITY = {
    'copper': {
        1.5: 24, 2.5: 32, 4: 42, 6: 55, 10: 75, 16: 100, 25: 140,
        35: 175, 50: 215, 70: 270, 95: 330, 120: 385, 150: 440,
        185: 510, 240: 600, 300: 690, 400: 830, 500: 950
    },
    'aluminum': {
        1.5: 18, 2.5: 25, 4: 32, 6: 42, 10: 55, 16: 75, 25: 100,
        35: 125, 50: 155, 70: 195, 95: 240, 120: 280, 150: 320,
        185: 370, 240: 440, 300: 505, 400: 610, 500: 700
    }
}


@dataclass
class CableCandidate:
    """电缆候选方案"""
    model: str          # 型号
    material: str       # 材料 (copper/aluminum)
    insulation: str     # 绝缘 (XLPE/PVC)
    section: float      # 截面 (mm²)
    voltage: int        # 电压 (V)
    length: float       # 长度 (m)

    economic_section: float = 0  # 经济截面
    technical_passed: bool = False
    technical_checks: Dict = None
    toc: Dict = None
    scores: Dict = None

    def __post_init__(self):
        if self.technical_checks is None:
            self.technical_checks = {}
        if self.toc is None:
            self.toc = {}
        if self.scores is None:
            self.scores = {}


class CableRecommender:
    """电缆型号推荐器"""

    def __init__(self, cable_prices: Optional[Dict] = None):
        """
        初始化推荐器

        Args:
            cable_prices: 自定义电缆价格表，如不提供则使用默认值
        """
        self.cable_prices = cable_prices or DEFAULT_CABLE_PRICES

    def build_candidates(self, params: Dict) -> List[CableCandidate]:
        """
        构建候选电缆集合

        Args:
            params: 输入参数

        Returns:
            候选电缆列表
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

        # 截面范围
        section_range = params.get('section_range', (1.5, 500))

        # 过滤标准截面
        sections = [s for s in STANDARD_SECTIONS 
                   if section_range[0] <= s <= section_range[1]]

        # 生成组合
        for material in materials:
            for insulation in insulations:
                model = model_map.get((material, insulation))
                if model:
                    for section in sections:
                        candidates.append(CableCandidate(
                            model=model,
                            material=material,
                            insulation=insulation,
                            section=section,
                            voltage=params.get('voltage', 10000),
                            length=params.get('length', 100)
                        ))

        return candidates

    def calculate_economic_section(self, params: Dict, material: str) -> Tuple[float, float]:
        """
        计算经济截面

        Args:
            params: 输入参数
            material: 导体材料

        Returns:
            (经济截面, 可变成本系数A)
        """
        I = params['current']
        L = params['length']
        h = params['hours']
        P_e = params['price_electricity']

        # 电阻率
        rho = RHO_CU if material == 'copper' else RHO_AL

        # 可变成本系数 A
        # A = (导体单价 × 密度) × 10^-6 [元/(m·mm²)]
        # 但实际电缆价格还包括绝缘、护套等，所以需要修正系数
        # 根据经验，总价格中导体成本约占50-70%
        price_per_kg = params['price_copper'] if material == 'copper' else params['price_aluminum']
        density = DENSITY_CU if material == 'copper' else DENSITY_AL

        # 导体部分的可变成本系数
        A_conductor = price_per_kg * density * 1e-6

        # 修正系数：电缆总价格中导体成本占比的倒数
        # 根据典型电缆价格数据推算
        conductor_cost_ratio = 0.65  # 导体成本占65%
        A = A_conductor / conductor_cost_ratio

        # 经济截面
        S_ec = I * math.sqrt(90 * rho * L * h * P_e / A)

        return S_ec, A

    def select_standard_section(self, S_ec: float, sections: List[float]) -> float:
        """
        选择大于等于 S_ec 的最小标准截面

        Args:
            S_ec: 经济截面
            sections: 标准截面列表

        Returns:
            选择的截面
        """
        for section in sorted(sections):
            if section >= S_ec:
                return section
        return sections[-1]

    def get_current_capacity(self, material: str, section: float, 
                           temperature: float = 40, method: str = 'air') -> float:
        """
        获取载流量

        Args:
            material: 导体材料
            section: 截面
            temperature: 环境温度
            method: 敷设方式

        Returns:
            载流量 (A)
        """
        # 基准载流量
        base_capacity = BASE_CURRENT_CAPACITY[material].get(section, 0)

        if base_capacity == 0:
            return 0

        # 温度修正（简化）
        # 假设基准温度为30℃
        temp_correction = 1.0
        if temperature != 30:
            if temperature > 30:
                temp_correction = 0.9  # 简化处理

        return base_capacity * temp_correction

    def calculate_voltage_drop(self, current: float, length: float, section: float,
                              material: str, voltage: float, power_factor: float = 0.85) -> Tuple[float, float]:
        """
        计算电压降

        Args:
            current: 电流 (A)
            length: 长度 (m)
            section: 截面 (mm²)
            material: 材料
            voltage: 电压 (V)
            power_factor: 功率因数

        Returns:
            (电压降V, 电压降%)
        """
        # 单位长度电阻
        rho = RHO_CU if material == 'copper' else RHO_AL
        R = rho / section

        # 总电阻
        total_resistance = R * length

        # 三相电压降（简化，忽略电抗）
        voltage_drop = math.sqrt(3) * current * total_resistance * power_factor

        # 电压降百分比
        voltage_drop_percent = (voltage_drop / voltage) * 100

        return voltage_drop, voltage_drop_percent

    def check_thermal_stability(self, section: float, material: str,
                               short_circuit_current: float, duration: float = 0.2) -> bool:
        """
        热稳定校核

        Args:
            section: 截面
            material: 材料
            short_circuit_current: 短路电流
            duration: 短路持续时间

        Returns:
            是否通过
        """
        K = K_CU if material == 'copper' else K_AL

        # 最小热稳定截面
        min_section = (short_circuit_current * 1000) / K * math.sqrt(duration)

        return section >= min_section

    def check_technical_constraints(self, params: Dict, candidate: CableCandidate) -> Tuple[bool, Dict]:
        """
        技术校核

        Args:
            params: 输入参数
            candidate: 候选电缆

        Returns:
            (是否通过, 详细信息)
        """
        info = {}

        # 载流量校核
        I_load = params['current']
        I_capacity = self.get_current_capacity(
            candidate.material,
            candidate.section,
            params.get('temperature', 40),
            params.get('installation_method', 'air')
        )
        info['current_capacity'] = {
            'required': I_load,
            'capacity': I_capacity,
            'passed': I_capacity >= I_load
        }

        # 电压降校核
        I_load = params['current']
        L = params['length']
        S = candidate.section
        V = params['voltage']
        cos_phi = params.get('power_factor', 0.85)
        voltage_drop_limit = params.get('voltage_drop_limit', 5.0)

        delta_U, delta_U_pct = self.calculate_voltage_drop(
            I_load, L, S, candidate.material, V, cos_phi
        )

        info['voltage_drop'] = {
            'value': delta_U,
            'percent': delta_U_pct,
            'limit': voltage_drop_limit,
            'passed': delta_U_pct <= voltage_drop_limit
        }

        # 热稳定校核
        I_sc = params.get('short_circuit_current', 25)
        t = params.get('short_circuit_duration', 0.2)

        thermal_passed = self.check_thermal_stability(
            S, candidate.material, I_sc, t
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

    def get_cable_price(self, model: str, section: float, voltage: int) -> float:
        """
        获取电缆单价

        Args:
            model: 电缆型号
            section: 截面
            voltage: 电压

        Returns:
            单价 (元/m)
        """
        # 简化：不考虑电压等级对价格的影响
        price_table = self.cable_prices.get(model, {})

        # 精确匹配
        if section in price_table:
            return price_table[section]

        # 插值估算
        sections = sorted(price_table.keys())
        if len(sections) < 2:
            return 0

        # 找到范围
        for i in range(len(sections) - 1):
            if sections[i] <= section <= sections[i + 1]:
                # 线性插值
                price1 = price_table[sections[i]]
                price2 = price_table[sections[i + 1]]
                return price1 + (price2 - price1) * (section - sections[i]) / (sections[i + 1] - sections[i])

        # 超出范围，使用最接近的
        if section < sections[0]:
            return price_table[sections[0]]
        else:
            return price_table[sections[-1]]

    def calculate_toc(self, params: Dict, candidate: CableCandidate) -> Dict:
        """
        计算总拥有成本

        Args:
            params: 输入参数
            candidate: 候选电缆

        Returns:
            TOC相关信息
        """
        # 电缆成本
        price_per_meter = self.get_cable_price(
            candidate.model,
            candidate.section,
            candidate.voltage
        )
        cable_cost = price_per_meter * candidate.length

        # N年损耗成本
        I_load = params['current']
        L = candidate.length
        S = candidate.section
        h = params['hours']
        P_e = params['price_electricity']
        N = params.get('years', 30)

        # 单位长度电阻
        rho = RHO_CU if candidate.material == 'copper' else RHO_AL
        R = rho / S

        # 三相总损耗功率
        P_loss = 3 * I_load**2 * R * L

        # N年总损耗成本
        loss_cost = (P_loss / 1000) * h * P_e * N

        # 总拥有成本
        total_cost = cable_cost + loss_cost

        # 投资回收期（简化）
        annual_loss_cost = loss_cost / N
        roi = cable_cost / annual_loss_cost if annual_loss_cost > 0 else float('inf')

        return {
            'cable_cost': cable_cost,
            'loss_cost': loss_cost,
            'total_cost': total_cost,
            'loss_per_year': annual_loss_cost,
            'roi': roi
        }

    def optimize_candidates(self, candidates: List[CableCandidate], params: Dict) -> List[CableCandidate]:
        """
        优化候选方案

        Args:
            candidates: 候选列表
            params: 输入参数

        Returns:
            优化后的候选列表（已排序）
        """
        # 筛选通过技术校核的方案
        valid_candidates = [c for c in candidates if c.technical_passed]

        if not valid_candidates:
            return []

        # 提取所有成本
        costs = [c.toc['total_cost'] for c in valid_candidates]
        min_cost = min(costs)
        max_cost = max(costs)

        # 计算评分
        w_eco = params.get('weight_economic', 1.0)
        w_rel = params.get('weight_reliability', 1.0)

        for candidate in valid_candidates:
            # 经济性评分（成本越低分越高）
            cost = candidate.toc['total_cost']
            if max_cost > min_cost:
                candidate.scores['economic'] = 1 - (cost - min_cost) / (max_cost - min_cost)
            else:
                candidate.scores['economic'] = 1

            # 可靠性评分（裕度）
            tech = candidate.technical_checks
            capacity_margin = tech['current_capacity']['capacity'] / tech['current_capacity']['required']
            voltage_drop_margin = tech['voltage_drop']['limit'] / tech['voltage_drop']['percent']

            # 归一化到0-1
            reliability_score = (min(capacity_margin, voltage_drop_margin) - 1) / 3
            candidate.scores['reliability'] = min(max(reliability_score, 0), 1)

            # 综合评分
            candidate.scores['overall'] = (
                w_eco * candidate.scores['economic'] +
                w_rel * candidate.scores['reliability']
            ) / (w_eco + w_rel)

        # 按综合评分排序
        valid_candidates.sort(key=lambda x: x.scores['overall'], reverse=True)

        return valid_candidates

    def recommend(self, params: Dict) -> Dict:
        """
        推荐最优电缆型号

        Args:
            params: 输入参数

        Returns:
            推荐结果
        """
        # 步骤1：构建候选集合
        candidates = self.build_candidates(params)

        # 步骤2：技术校核 + 计算 TOC
        for candidate in candidates:
            passed, checks = self.check_technical_constraints(params, candidate)
            candidate.technical_passed = passed
            candidate.technical_checks = checks

            # 计算 TOC（仅对通过技术校核的）
            if passed:
                candidate.toc = self.calculate_toc(params, candidate)
            else:
                candidate.toc = {'total_cost': float('inf')}

        # 步骤3：优化
        optimized = self.optimize_candidates(candidates, params)

        # 步骤4：计算经济截面（用于报告）
        for material in ['copper', 'aluminum']:
            S_ec, A = self.calculate_economic_section(params, material)
            for candidate in candidates:
                if candidate.material == material:
                    candidate.economic_section = S_ec

        # 步骤5：生成结果
        if not optimized:
            return {
                'success': False,
                'error': '没有通过技术校核的方案',
                'all_candidates': [asdict(c) for c in candidates]
            }

        best = optimized[0]

        # 生成对比
        comparison = []
        for i, candidate in enumerate(optimized[1:6], 1):  # 前5个对比
            comparison.append({
                'rank': i + 1,
                'model': candidate.model,
                'material': candidate.material,
                'section': candidate.section,
                'voltage': candidate.voltage,
                'total_cost': candidate.toc['total_cost'],
                'difference': candidate.toc['total_cost'] - best.toc['total_cost'],
                'overall_score': candidate.scores['overall']
            })

        # 生成推理说明
        reasoning = self._generate_reasoning(best, params, comparison)

        return {
            'success': True,
            'best_candidate': {
                'model': best.model,
                'material': best.material,
                'insulation': best.insulation,
                'section': best.section,
                'voltage': best.voltage,
                'length': best.length
            },
            'technical_checks': best.technical_checks,
            'economic_analysis': {
                'economic_section': round(best.economic_section, 2),
                'selected_section': best.section,
                'cable_cost': round(best.toc['cable_cost'], 2),
                'loss_cost_per_year': round(best.toc['loss_per_year'], 2),
                'total_cost_30years': round(best.toc['total_cost'], 2),
                'roi': round(best.toc['roi'], 2)
            },
            'scores': best.scores,
            'comparison': comparison,
            'reasoning': reasoning
        }

    def _generate_reasoning(self, best: CableCandidate, params: Dict, comparison: List[Dict]) -> str:
        """生成推理说明"""
        reasoning_parts = []

        # 材料选择
        if best.material == 'copper':
            reasoning_parts.append(f"选择铜芯电缆，因为虽然铜芯成本较高，但其经济电流密度高（约{best.economic_section/best.section:.2f}），在{params['hours']}h年运行条件下总拥有成本最低。")
        else:
            reasoning_parts.append(f"选择铝芯电缆，因为在大负荷长时运行条件下，铝芯的材料成本优势显著，尽管需要更大截面({best.section}mm² vs 约{best.economic_section*0.5:.0f}mm²铜芯)，但总拥有成本更低。")

        # 截面选择
        reasoning_parts.append(f"经济截面计算值为{best.economic_section:.2f}mm²，选择标准截面{best.section}mm²，满足所有技术约束。")

        # 技术裕度
        tech = best.technical_checks
        capacity_margin = tech['current_capacity']['capacity'] / tech['current_capacity']['required']
        reasoning_parts.append(f"载流量裕度为{(capacity_margin-1)*100:.1f}%，电压降为{tech['voltage_drop']['percent']:.3f}%（限制{tech['voltage_drop']['limit']}%），热稳定校验{'通过' if tech['thermal_stability']['passed'] else '不通过'}。")

        # 经济性
        reasoning_parts.append(f"30年总拥有成本为{best.toc['total_cost']:.0f}元，其中电缆成本占{best.toc['cable_cost']/best.toc['total_cost']*100:.1f}%，损耗成本占{best.toc['loss_cost']/best.toc['total_cost']*100:.1f}%。")

        return " ".join(reasoning_parts)

    def format_result(self, result: Dict) -> str:
        """格式化输出结果"""
        if not result.get('success'):
            return f"❌ 推荐失败: {result.get('error')}"

        best = result['best_candidate']
        tech = result['technical_checks']
        eco = result['economic_analysis']
        comparison = result.get('comparison', [])

        output = f"""
{'='*70}
🎯 最优电缆型号推荐结果
{'='*70}

【推荐方案】
  电缆型号: {best['model']}-{best['voltage']/1000:.0f}kV-3×{best['section']}
  导体材料: {best['material']}
  绝缘类型: {best['insulation']}
  电缆长度: {best['length']} m

【技术校核】
  ✓ 载流量校验: 需要 {tech['current_capacity']['required']:.0f}A，载流量 {tech['current_capacity']['capacity']:.0f}A
  ✓ 电压降校验: {tech['voltage_drop']['percent']:.3f}% （限制 {tech['voltage_drop']['limit']}%）
  ✓ 热稳定校验: 短路电流 {tech['thermal_stability']['short_circuit_current']}kA，{tech['thermal_stability']['duration']}s

【经济性分析】
  经济截面: {eco['economic_section']:.2f} mm²
  选择截面: {eco['selected_section']} mm²
  电缆成本: ¥{eco['cable_cost']:,.0f}
  年损耗成本: ¥{eco['loss_cost_per_year']:,.2f}
  30年总成本: ¥{eco['total_cost_30years']:,.0f}
  投资回收期: {eco['roi']:.1f} 年

【综合评分】
  经济性: {result['scores']['economic']:.3f}
  可靠性: {result['scores']['reliability']:.3f}
  综合评分: {result['scores']['overall']:.3f}
"""

        if comparison:
            output += f"\n【对比方案（前3）】\n"
            for comp in comparison[:3]:
                diff_sign = "+" if comp['difference'] > 0 else ""
                output += f"  {comp['rank']}. {comp['model']}-{comp['voltage']/1000:.0f}kV-3×{comp['section']} ({comp['material']})\n"
                output += f"     成本: ¥{comp['total_cost']:,.0f} ({diff_sign}{comp['difference']:.0f})\n"

        output += f"\n【推荐理由】\n{result['reasoning']}\n"
        output += f"{'='*70}\n"

        return output


def main():
    """主函数"""
    recommender = CableRecommender()

    # 示例参数
    params = {
        # 运行参数
        'current': 200,              # 负荷电流 A
        'length': 100,               # 电缆长度 m
        'voltage': 10000,            # 电压等级 V
        'hours': 5000,               # 年运行小时数 h
        'power_factor': 0.85,        # 功率因数

        # 经济参数
        'price_electricity': 0.8,    # 电价 元/kWh
        'price_copper': 65,          # 铜价格 元/kg
        'price_aluminum': 18,        # 铝价格 元/kg
        'years': 30,                 # 分析周期 年

        # 技术约束
        'voltage_drop_limit': 5.0,   # 允许电压降 %
        'short_circuit_current': 25, # 短路电流 kA
        'short_circuit_duration': 0.2, # 短路持续时间 s
        'temperature': 40,           # 环境温度 ℃

        # 可选范围
        'materials': ['copper', 'aluminum'],
        'insulations': ['XLPE', 'PVC'],
        'section_range': (10, 500),

        # 优化权重
        'weight_economic': 1.0,
        'weight_reliability': 1.0,
    }

    # 推荐
    result = recommender.recommend(params)

    # 输出
    print(recommender.format_result(result))


if __name__ == '__main__':
    main()
