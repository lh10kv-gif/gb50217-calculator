# -*- coding: utf-8 -*-
"""
电缆全生命周期经济选型工具 V5 (基于GB50217-2018及配电设计手册第四版)

V5更新：
  - 经济电流密度按GB50217附录B公式动态计算
  - 根据实际电价、铜价、贴现率、经济寿命自动调整Jec
  - 经济截面与LCC最优截面高度一致（差异≤1个规格）

V3功能：
  - 载流量校验（确保电缆不过载运行）
  - 电压降校核（默认限值5%）
  - 温度、敷设方式校正系数

电缆型号：
  - 铜芯电缆：YJY22（XLPE绝缘钢带铠装PE护套电力电缆）
  - 铝合金电缆：YJLHY22（XLPE绝缘铝合金导体钢带铠装PE护套电力电缆）

芯数规则：
  - 10kV电缆：3芯
  - 1kV电缆：4芯

选型逻辑：
  经济截面 = Imax / Jec（Jec按GB公式动态计算）
  最小要求截面 = max(热稳定截面, 载流量截面, 电压降截面)
  若经济截面 ≥ 最小要求截面，按经济选型
  若经济截面 < 最小要求截面，按最小要求截面选型
"""

import sys
import math
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit, QFormLayout,
                             QComboBox, QDoubleSpinBox, QSpinBox, QMessageBox, QScrollArea,
                             QGroupBox, QCheckBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


# ==================== 常量定义 ====================

# 材料密度 (g/cm³)
CU_DENSITY = 8.96  # 铜密度
AL_DENSITY = 2.70  # 铝密度

# 线芯占比系数
CONDUCTOR_RATIO = {
    ('铜', '10kV'): 0.85,
    ('铜', '1kV'): 0.90,
    ('铝', '10kV'): 0.70,
    ('铝', '1kV'): 0.80,
}

# 通道费用 (元/m)
CHANNEL_COST = {
    '直埋': 150,
    '穿管': 300,
    '桥架': 100,
    '预留电缆沟': 40,
}

# 附件费率
ATTACHMENT_RATE = {
    '10kV': 0.10,  # 10kV: 电缆成本 × 10%
    '1kV': 0.02,   # 1kV: 电缆成本 × 2%
}

# 其他费用系数
OTHER_COST_RATE = 0.08  # (电缆成本 + 通道费用) × 8%

# 热稳定系数 C值
THERMAL_STABILITY_FACTOR = {
    '铜': 137,
    '铝': 93,
}

# ==================== 载流量数据表 (基于GB50217-2018 附录C) ====================
# 基准条件：土壤直埋敷设，土壤温度25℃，热阻系数2.0 K·m/W，XLPE绝缘(90℃)
# 数据来源：GB50217-2018 附录C《10kV及以下常用电力电缆100%持续允许载流量》
# 注：表中系铝芯电缆数值，铜芯电缆载流量 = 铝芯 × 1.29
# 单位：A

# =====================================================
# 表C.0.3：10kV三芯交联聚乙烯绝缘电缆持续允许载流量
# 适用：铝芯电缆，有钢铠护套，直埋敷设
# =====================================================
AL_10KV_3CORE_BURIED = {
    25: 90, 35: 105, 50: 120, 70: 152, 95: 182,
    120: 205, 150: 219, 185: 247, 240: 292, 300: 328,
    400: 374, 500: 424
}

# 10kV三芯铜芯电缆载流量 = 铝芯 × 1.29
CU_10KV_3CORE_BURIED = {k: int(v * 1.29) for k, v in AL_10KV_3CORE_BURIED.items()}

# =====================================================
# 表C.0.1-4：1kV～3kV交联聚乙烯绝缘电缆直埋敷设载流量
# 适用：铝芯电缆，3芯，热阻系数2.0 K·m/W
# 4芯电缆载流量约为3芯的0.95倍（工程经验值）
# =====================================================
AL_1KV_3CORE_BURIED = {
    25: 91, 35: 113, 50: 134, 70: 165, 95: 195,
    120: 221, 150: 247, 185: 278, 240: 321, 300: 365
}

# 1kV四芯铝芯电缆载流量 = 3芯 × 0.95
AL_1KV_4CORE_BURIED = {k: int(v * 0.95) for k, v in AL_1KV_3CORE_BURIED.items()}

# 1kV三芯/四芯铜芯电缆载流量 = 铝芯 × 1.29
CU_1KV_3CORE_BURIED = {k: int(v * 1.29) for k, v in AL_1KV_3CORE_BURIED.items()}
CU_1KV_4CORE_BURIED = {k: int(v * 1.29) for k, v in AL_1KV_4CORE_BURIED.items()}

# 组合数据表（用于程序调用）
CU_CURRENT_CAPACITY_BURIED = {
    10: CU_10KV_3CORE_BURIED,
    1: CU_1KV_4CORE_BURIED
}

AL_CURRENT_CAPACITY_BURIED = {
    10: AL_10KV_3CORE_BURIED,
    1: AL_1KV_4CORE_BURIED
}

# 敷设方式校正系数 (相对于直埋)
INSTALL_CORRECTION_FACTOR = {
    '直埋': 1.00,
    '穿管': 0.85,      # 穿管散热差
    '桥架': 1.10,      # 空气中散热好
    '预留电缆沟': 0.95  # 电缆沟散热一般
}

# 土壤热阻系数校正系数（基准：2.0 K·m/W）
# 数据来源：GB50217-2018，热阻系数降低时载流量增加
SOIL_RESISTIVITY_FACTOR = {
    0.8: 1.22,   # 湿润土壤（散热好，载流量增大22%）
    1.0: 1.15,   # 潮湿土壤
    1.2: 1.08,   # 较湿土壤
    1.5: 1.04,   # 一般土壤
    2.0: 1.00,   # 基准值（GB50217附录C.0.3标准条件）
    2.5: 0.94,   # 较干土壤
    3.0: 0.88    # 干燥沙土（散热差，载流量降低12%）
}


class CableCalculator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("电缆全生命周期经济选型工具 V5 (GB50217-2018)")
        self.resize(1100, 950)
        
        # 设置全局字体 - 放大2号（默认9pt → 11pt）
        font = QFont("Microsoft YaHei", 11)
        self.setFont(font)
        
        self.init_ui()

    def init_ui(self):
        # 主部件和布局
        container = QWidget()
        self.setCentralWidget(container)
        main_layout = QVBoxLayout(container)

        # 创建滚动区域以容纳表单
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        form_layout = QFormLayout(scroll_content)

        # --- 电缆基础参数 ---
        form_layout.addRow(QLabel("<h3>1. 电缆基础参数</h3>"))

        self.voltage_combo = QComboBox()
        self.voltage_combo.addItems(["10kV (3芯电缆)", "1kV (4芯电缆)"])
        form_layout.addRow("电压等级:", self.voltage_combo)

        self.material_combo = QComboBox()
        self.material_combo.addItems(["铜芯", "铝芯"])
        form_layout.addRow("导体材料:", self.material_combo)

        self.imax_input = QDoubleSpinBox()
        self.imax_input.setRange(0, 10000)
        self.imax_input.setSuffix(" A")
        self.imax_input.setSingleStep(10)
        self.imax_input.setDecimals(1)
        form_layout.addRow("最大持续工作电流 Imax:", self.imax_input)

        self.tmax_input = QSpinBox()
        self.tmax_input.setRange(0, 8760)
        self.tmax_input.setSuffix(" h")
        self.tmax_input.setValue(4500)
        form_layout.addRow("年最大负荷利用小时数 Tmax:", self.tmax_input)

        self.cosphi_input = QDoubleSpinBox()
        self.cosphi_input.setRange(0.1, 1.0)
        self.cosphi_input.setValue(0.9)
        self.cosphi_input.setSingleStep(0.01)
        self.cosphi_input.setDecimals(2)
        form_layout.addRow("功率因数 cosφ:", self.cosphi_input)

        self.length_input = QDoubleSpinBox()
        self.length_input.setRange(0, 100000)
        self.length_input.setSuffix(" m")
        self.length_input.setValue(100)
        self.length_input.setDecimals(1)
        form_layout.addRow("电缆长度 L:", self.length_input)

        self.voltage_drop_input = QDoubleSpinBox()
        self.voltage_drop_input.setRange(1, 10)
        self.voltage_drop_input.setSuffix(" %")
        self.voltage_drop_input.setValue(5.0)  # 默认5%
        self.voltage_drop_input.setSingleStep(0.5)
        self.voltage_drop_input.setDecimals(1)
        form_layout.addRow("允许电压降:", self.voltage_drop_input)

        # --- 环境与短路参数 ---
        form_layout.addRow(QLabel("<h3>2. 环境与短路参数</h3>"))

        self.install_combo = QComboBox()
        self.install_combo.addItems(["直埋", "穿管", "桥架", "预留电缆沟"])
        self.install_combo.currentIndexChanged.connect(self.update_channel_cost)
        form_layout.addRow("敷设方式:", self.install_combo)

        self.temp_input = QDoubleSpinBox()
        self.temp_input.setRange(-20, 60)
        self.temp_input.setSuffix(" ℃")
        self.temp_input.setValue(25)  # 默认25℃
        self.temp_input.setDecimals(1)
        form_layout.addRow("环境温度:", self.temp_input)

        self.soil_resistivity_combo = QComboBox()
        self.soil_resistivity_combo.addItems([
            "0.8 K·m/W (湿润土壤)",
            "1.0 K·m/W (标准土壤)",
            "1.2 K·m/W",
            "1.5 K·m/W",
            "2.0 K·m/W (干燥沙土)",
            "2.5 K·m/W",
            "3.0 K·m/W (极干土壤)"
        ])
        form_layout.addRow("土壤热阻系数:", self.soil_resistivity_combo)

        self.ik_input = QDoubleSpinBox()
        self.ik_input.setRange(0, 50)
        self.ik_input.setSuffix(" kA")
        self.ik_input.setValue(20)  # 默认20kA
        self.ik_input.setSingleStep(1)
        self.ik_input.setDecimals(1)
        form_layout.addRow("短路电流 Ik (有效值):", self.ik_input)

        self.time_input = QDoubleSpinBox()
        self.time_input.setRange(0.01, 5.0)
        self.time_input.setSuffix(" s")
        self.time_input.setValue(0.1)  # 默认0.1秒
        self.time_input.setSingleStep(0.01)
        self.time_input.setDecimals(2)
        form_layout.addRow("短路持续时间 t:", self.time_input)

        # --- 价格参数 ---
        form_layout.addRow(QLabel("<h3>3. 价格参数</h3>"))
        form_layout.addRow(QLabel("<i>电缆价格根据原材料价格实时计算</i>"))

        self.cu_price_input = QDoubleSpinBox()
        self.cu_price_input.setRange(0, 500000)
        self.cu_price_input.setSuffix(" 元/吨")
        self.cu_price_input.setValue(100000)  # 默认100000元/吨
        self.cu_price_input.setSingleStep(5000)
        self.cu_price_input.setDecimals(0)
        form_layout.addRow("铜价:", self.cu_price_input)

        self.al_price_input = QDoubleSpinBox()
        self.al_price_input.setRange(0, 100000)
        self.al_price_input.setSuffix(" 元/吨")
        self.al_price_input.setValue(25000)  # 默认25000元/吨
        self.al_price_input.setSingleStep(1000)
        self.al_price_input.setDecimals(0)
        form_layout.addRow("铝价:", self.al_price_input)

        # --- 通道费用 ---
        form_layout.addRow(QLabel("<h3>4. 通道费用</h3>"))

        self.channel_cost_input = QDoubleSpinBox()
        self.channel_cost_input.setRange(0, 1000)
        self.channel_cost_input.setSuffix(" 元/m")
        self.channel_cost_input.setValue(150)  # 默认直埋150元/m
        self.channel_cost_input.setSingleStep(10)
        self.channel_cost_input.setDecimals(0)
        form_layout.addRow("通道费用:", self.channel_cost_input)

        # --- 经济参数 ---
        form_layout.addRow(QLabel("<h3>5. 经济参数</h3>"))
        form_layout.addRow(QLabel("<i>用于全生命周期成本(LCC)分析</i>"))

        self.economic_life_input = QSpinBox()
        self.economic_life_input.setRange(1, 50)
        self.economic_life_input.setSuffix(" 年")
        self.economic_life_input.setValue(30)
        form_layout.addRow("经济寿命:", self.economic_life_input)

        self.discount_rate_input = QDoubleSpinBox()
        self.discount_rate_input.setRange(0, 20)
        self.discount_rate_input.setSuffix(" %")
        self.discount_rate_input.setValue(6.0)  # 默认6%
        self.discount_rate_input.setSingleStep(0.5)
        self.discount_rate_input.setDecimals(2)
        form_layout.addRow("贴现率:", self.discount_rate_input)

        self.electricity_price_input = QDoubleSpinBox()
        self.electricity_price_input.setRange(0, 10)
        self.electricity_price_input.setSuffix(" 元/kWh")
        self.electricity_price_input.setValue(0.4)  # 默认0.4元/kWh
        self.electricity_price_input.setSingleStep(0.01)
        self.electricity_price_input.setDecimals(2)
        form_layout.addRow("电价:", self.electricity_price_input)

        self.maintenance_rate_input = QDoubleSpinBox()
        self.maintenance_rate_input.setRange(0, 20)
        self.maintenance_rate_input.setSuffix(" 元/m·年")
        self.maintenance_rate_input.setValue(5.00)  # 默认5.00元/m·年
        self.maintenance_rate_input.setSingleStep(0.5)
        self.maintenance_rate_input.setDecimals(2)
        form_layout.addRow("运维费用:", self.maintenance_rate_input)

        # --- 按钮 ---
        btn_layout = QHBoxLayout()
        self.calc_btn = QPushButton("开始计算")
        self.calc_btn.clicked.connect(self.calculate)
        self.calc_btn.setStyleSheet("font-size: 16px; padding: 10px 25px;")
        btn_layout.addStretch()
        btn_layout.addWidget(self.calc_btn)

        # --- 结果显示 ---
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setStyleSheet("font-family: 'Consolas', 'Courier New', 'Microsoft YaHei', monospace; font-size: 12pt;")

        # 组装布局
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(QLabel("<b>计算结果:</b>"))
        main_layout.addWidget(self.result_text)

    def update_channel_cost(self):
        """根据敷设方式更新通道费用"""
        method = self.install_combo.currentText()
        cost = CHANNEL_COST.get(method, 150)
        self.channel_cost_input.setValue(cost)

    def get_jec(self, tmax, is_copper, voltage, cu_price, al_price, electricity_price, discount_rate, years):
        """根据实际参数按GB50217附录B公式计算经济电流密度 Jec (A/mm²)
        
        公式推导：
        LCC = a × S × L + (3 × I² × ρ × L × τ × C2 / (1000 × S)) × N
        对S求导，令dLCC/dS = 0：
        S = I × √(3 × ρ × τ × C2 × N / (1000 × a))
        Jec = I / S = √(1000 × a / (3 × ρ × τ × C2 × N))
        
        其中：
        - a: 电缆单位截面成本 (元/mm²·m)
        - ρ: 导体电阻率 (Ω·mm²/m)
        - τ: 最大损耗小时数 (h)
        - C2: 电价 (元/kWh)
        - N: 年金现值系数
        """
        # 1. 电阻率 ρ (Ω·mm²/m)
        # 铜: 0.017241, 铝: 0.028264
        rho = 0.017241 if is_copper else 0.028264
        
        # 2. 估算τ (简化计算)
        if tmax < 2000:
            tau = 1000
        elif tmax < 3000:
            tau = 1500 + (tmax - 2000) * 0.5
        elif tmax < 4000:
            tau = 2000 + (tmax - 3000) * 0.8
        elif tmax < 5000:
            tau = 2800 + (tmax - 4000) * 1.0
        elif tmax < 6000:
            tau = 3800 + (tmax - 5000) * 1.2
        else:
            tau = 5000 + (tmax - 6000) * 1.0
        
        # 3. 计算电缆成本系数 a (元/mm²·m)
        cores = 3 if voltage == 10 else 4
        density = CU_DENSITY if is_copper else AL_DENSITY
        price_per_kg = (cu_price if is_copper else al_price) / 1000  # 元/kg
        material = '铜' if is_copper else '铝'
        voltage_str = '10kV' if voltage == 10 else '1kV'
        ratio = CONDUCTOR_RATIO[(material, voltage_str)]
        
        # a = 单位截面的线芯成本 / 线芯占比
        a = cores * density / 1000 * price_per_kg / ratio
        
        # 4. 电价 C2
        C2 = electricity_price
        
        # 5. 年金现值系数 N
        if discount_rate <= 0:
            N = years
        else:
            r = discount_rate / 100.0
            N = (1 - math.pow(1 + r, -years)) / r
        
        # 6. 计算经济电流密度
        # Jec = √(1000 × a / (3 × ρ × τ × C2 × N))
        numerator = 1000 * a
        denominator = 3 * rho * tau * C2 * N
        
        if denominator <= 0:
            # 异常情况，返回GB表格参考值
            if is_copper:
                return 2.25 if tmax < 5000 else 2.00
            else:
                return 1.54 if tmax < 5000 else 1.38
        
        Jec = math.sqrt(numerator / denominator)
        
        return Jec, tau

    def get_tau(self, tmax, cosphi):
        """根据Tmax和cosphi查表内插计算τ (最大损耗时间)
        
        基于配电设计手册第四版
        """
        tau_table = {
            2000: [1500, 1200, 1000, 800],
            2500: [1700, 1500, 1250, 1100],
            3000: [2000, 1800, 1600, 1400],
            3500: [2350, 2150, 2000, 1800],
            4000: [2750, 2600, 2400, 2200],
            4500: [3150, 3000, 2900, 2700],
            5000: [3600, 3500, 3400, 3200],
            5500: [4100, 4000, 3950, 3750],
            6000: [4650, 4600, 4500, 4350],
            7000: [5950, 5900, 5800, 5700]
        }

        if cosphi < 0.825:
            c_idx = 0
        elif cosphi < 0.875:
            c_idx = 1
        elif cosphi < 0.925:
            c_idx = 2
        else:
            c_idx = 3

        keys = sorted(tau_table.keys())
        k1, k2 = keys[0], keys[-1]
        for i in range(len(keys)-1):
            if keys[i] <= tmax < keys[i+1]:
                k1, k2 = keys[i], keys[i+1]
                break

        tau1 = tau_table[k1][c_idx]
        tau2 = tau_table[k2][c_idx]
        tau = tau1 + (tmax - k1) * (tau2 - tau1) / (k2 - k1)
        return tau

    def get_resistance(self, section, voltage, is_copper):
        """根据截面、电压等级和材料类型获取交流电阻 (Ω/km)
        
        基于配电设计手册第四版
        公式：R = K / S
        """
        if is_copper:
            k = 18.5 if voltage == 10 else 20.0
        else:
            k = 30.3 if voltage == 10 else 32.8
        
        return k / section

    def get_reactance(self, section, voltage):
        """获取电抗 (Ω/km)
        
        根据配电设计手册第四版
        """
        if voltage == 1:
            return 0.08
        else:  # 10kV
            return 0.09

    def get_current_capacity(self, section, voltage, is_copper, temp=25, install_method='直埋', soil_resistivity=1.0):
        """计算电缆载流量 (A)
        
        基于GB50217-2018计算载流量
        
        公式：I = I_ref × K_t × K_install × K_soil
        
        参数：
            section: 截面 (mm²)
            voltage: 电压等级 (10 或 1)
            is_copper: 是否为铜芯
            temp: 环境温度 (℃)
            install_method: 敷设方式
            soil_resistivity: 土壤热阻系数 (K·m/W)
        """
        # 获取参考载流量
        if is_copper:
            ref_capacity = CU_CURRENT_CAPACITY_BURIED[voltage].get(section, 0)
        else:
            ref_capacity = AL_CURRENT_CAPACITY_BURIED[voltage].get(section, 0)
        
        # 温度修正系数
        # 参考温度 θ_ref = 25℃（土壤直埋标准）
        # 导体最高允许工作温度 θ_m = 90℃（XLPE绝缘）
        t_max = 90  # XLPE绝缘最高温度
        t_ref = 25  # GB50217土壤直埋参考温度
        k_temp = math.sqrt((t_max - temp) / (t_max - t_ref))
        
        # 敷设方式修正系数
        k_install = INSTALL_CORRECTION_FACTOR.get(install_method, 1.0)
        
        # 土壤热阻修正系数
        k_soil = SOIL_RESISTIVITY_FACTOR.get(soil_resistivity, 1.0)
        
        # 计算最终载流量
        final_capacity = ref_capacity * k_temp * k_install * k_soil
        
        return final_capacity

    def calculate_voltage_drop(self, section, voltage, is_copper, current, length_km, cosphi):
        """计算电压降 (%)
        
        根据配电设计手册第四版公式：
        ΔU% = √3 × I × (R×cosφ + X×sinφ) × L / U × 100%
        
        参数：
            section: 截面 (mm²)
            voltage: 电压等级 (10 或 1)
            is_copper: 是否为铜芯
            current: 负荷电流 (A)
            length_km: 长度 (km)
            cosphi: 功率因数
        """
        # 获取电阻和电抗
        r = self.get_resistance(section, voltage, is_copper)
        x = self.get_reactance(section, voltage)
        
        # 计算电压降（V）
        voltage_v = voltage * 1000  # 转换为V
        sinphi = math.sqrt(1 - cosphi ** 2)  # sinφ
        voltage_drop_v = math.sqrt(3) * current * (r * cosphi + x * sinphi) * length_km
        
        # 计算电压降百分比
        voltage_drop_pct = (voltage_drop_v / voltage_v) * 100
        
        return voltage_drop_pct

    def calculate_pv_factor(self, discount_rate, years):
        """计算年金现值系数"""
        if discount_rate <= 0:
            return years
        r = discount_rate / 100.0
        pv_factor = (1 - math.pow(1 + r, -years)) / r
        return pv_factor

    def get_standard_sections(self):
        """返回标准电缆截面序列 (mm²)"""
        return [25, 35, 50, 70, 95, 120, 150, 185, 240, 300, 400, 500, 630, 800]

    def calculate_cable_price(self, section, voltage, is_copper, cu_price, al_price):
        """计算电缆价格 (元/m)
        
        公式：
            线芯重量(kg/m) = 截面(mm²) × 芯数 × 密度(g/cm³) / 1000
            线芯价格(元/m) = 线芯重量 × 单价(元/kg)
            电缆价格(元/m) = 线芯价格 / 线芯占比
        """
        cores = 3 if voltage == 10 else 4
        material = '铜' if is_copper else '铝'
        voltage_str = '10kV' if voltage == 10 else '1kV'
        
        if is_copper:
            density = CU_DENSITY
            price_per_kg = cu_price / 1000
        else:
            density = AL_DENSITY
            price_per_kg = al_price / 1000
        
        conductor_weight = section * cores * density / 1000
        conductor_cost = conductor_weight * price_per_kg
        ratio = CONDUCTOR_RATIO[(material, voltage_str)]
        cable_price = conductor_cost / ratio
        
        return cable_price

    def calculate_initial_investment(self, section, length, voltage, is_copper, cu_price, al_price, channel_cost):
        """计算初始投资
        
        初始投资 = 电缆成本 + 通道费用 + 附件费用 + 其他费用
        """
        cable_price = self.calculate_cable_price(section, voltage, is_copper, cu_price, al_price)
        cable_cost = cable_price * length
        channel_total = channel_cost * length
        voltage_str = '10kV' if voltage == 10 else '1kV'
        attachment_rate = ATTACHMENT_RATE[voltage_str]
        attachment_cost = cable_cost * attachment_rate
        other_cost = (cable_cost + channel_total) * OTHER_COST_RATE
        total_investment = cable_cost + channel_total + attachment_cost + other_cost
        
        return {
            'total': total_investment,
            'cable_cost': cable_cost,
            'cable_price': cable_price,
            'channel_cost': channel_total,
            'attachment_cost': attachment_cost,
            'other_cost': other_cost,
        }

    def calculate(self):
        try:
            # 获取输入值
            voltage_str = self.voltage_combo.currentText()
            voltage = 10 if "10kV" in voltage_str else 1
            is_copper = self.material_combo.currentText() == "铜芯"
            material_name = "铜芯" if is_copper else "铝芯"
            
            imax = self.imax_input.value()
            tmax = self.tmax_input.value()
            cosphi = self.cosphi_input.value()
            length = self.length_input.value()
            length_km = length / 1000.0
            
            # 环境与短路参数
            temp = self.temp_input.value()
            ik_kA = self.ik_input.value()
            t_sec = self.time_input.value()
            install_method = self.install_combo.currentText()
            allowed_voltage_drop = self.voltage_drop_input.value()
            
            # 土壤热阻系数
            soil_text = self.soil_resistivity_combo.currentText()
            soil_resistivity = float(soil_text.split()[0])
            
            # 价格参数
            cu_price = self.cu_price_input.value()
            al_price = self.al_price_input.value()
            channel_cost = self.channel_cost_input.value()
            
            # 经济参数
            economic_life = self.economic_life_input.value()
            discount_rate = self.discount_rate_input.value()
            electricity_price = self.electricity_price_input.value()
            maintenance_rate = self.maintenance_rate_input.value()
            
            # 计算年金现值系数
            pv_factor = self.calculate_pv_factor(discount_rate, economic_life)

            # ===== 选型校验计算 =====
            
            # 1. 经济电流密度计算（按GB50217附录B公式）
            jec_result = self.get_jec(tmax, is_copper, voltage, cu_price, al_price, 
                                    electricity_price, discount_rate, economic_life)
            if isinstance(jec_result, tuple):
                jec, tau = jec_result
            else:
                jec = jec_result
                tau = 3000  # 默认值
            s_eco = imax / jec

            # 2. 热稳定校验
            c_factor = THERMAL_STABILITY_FACTOR['铜' if is_copper else '铝']
            ik_a = ik_kA * 1000
            s_min_thermal = (ik_a * (t_sec ** 0.5)) / c_factor

            # 4. 载流量校验 - 计算满足载流量的最小截面
            sections = self.get_standard_sections()
            s_min_ampacity = None
            for s in sections:
                capacity = self.get_current_capacity(s, voltage, is_copper, temp, install_method, soil_resistivity)
                if capacity >= imax:
                    s_min_ampacity = s
                    break

            if s_min_ampacity is None:
                s_min_ampacity = max(sections)
                result_text = "⚠️  警告: 无截面满足载流量要求，已选最大规格。\n\n"
            else:
                result_text = ""

            # 5. 电压降校验 - 计算满足电压降的最小截面
            s_min_voltage = None
            for s in sections:
                voltage_drop = self.calculate_voltage_drop(s, voltage, is_copper, imax, length_km, cosphi)
                if voltage_drop <= allowed_voltage_drop:
                    s_min_voltage = s
                    break

            if s_min_voltage is None:
                s_min_voltage = max(sections)
                result_text += "⚠️  警告: 无截面满足电压降要求，已选最大规格。\n\n"

            # 6. 确定最小要求截面
            s_min_required = max(s_min_thermal, s_min_ampacity, s_min_voltage)

            # 7. 确定候选方案 - 【重要】从最小要求截面开始对比
            # 候选截面必须全部 >= s_min_required（确保满足技术条件）
            # 对比从最小要求截面开始，让用户看到完整的经济性变化趋势
            
            # 先筛选出所有满足技术条件的截面
            valid_sections = [s for s in sections if s >= s_min_required]
            
            if not valid_sections:
                valid_sections = [max(sections)]
                result_text += "⚠️  严重警告: 无截面满足技术条件，已选最大规格。\n\n"

            # 从最小要求截面开始，取后续最多8个规格作为候选
            start_index = 0
            for i, s in enumerate(valid_sections):
                if s >= s_min_required:
                    start_index = i
                    break
            
            # 候选方案：从最小要求截面开始，取后续最多8个（全部满足技术条件）
            candidate_sections = valid_sections[start_index:min(start_index + 8, len(valid_sections))]

            # ===== 输出报告 =====
            result_text += f"{'='*110}\n"
            result_text += f"电缆全生命周期经济选型计算报告 V5\n"
            result_text += f"{'='*110}\n\n"
            
            # 基本信息
            cores = 3 if voltage == 10 else 4
            cable_model = "YJY22" if is_copper else "YJLHY22"
            
            result_text += f"【电缆型号】{cable_model}-{voltage}kV-{cores}芯\n"
            result_text += f"{'-'*110}\n\n"
            
            result_text += f"【基本参数】\n"
            result_text += f"{'-'*110}\n"
            result_text += f"材料类型: {material_name}\n"
            result_text += f"负荷电流: {imax:.1f}A | Tmax: {tmax}h | cosφ: {cosphi:.2f}\n"
            result_text += f"电缆长度: {length:.1f}m | 电压等级: {voltage}kV | 芯数: {cores}芯\n"
            result_text += f"短路电流: {ik_kA:.1f}kA | 持续时间: {t_sec:.2f}s | 环境温度: {temp:.1f}℃\n"
            result_text += f"允许电压降: {allowed_voltage_drop}%\n"
            result_text += f"敷设方式: {install_method} | 土壤热阻: {soil_resistivity} K·m/W\n\n"

            result_text += f"【价格参数】\n"
            result_text += f"{'-'*110}\n"
            result_text += f"铜价: {cu_price:.0f} 元/吨 | 铝价: {al_price:.0f} 元/吨\n"
            result_text += f"通道费用: {channel_cost:.0f} 元/m\n\n"

            result_text += f"【经济参数】\n"
            result_text += f"{'-'*110}\n"
            result_text += f"经济寿命: {economic_life} 年\n"
            result_text += f"贴现率: {discount_rate:.2f}% | 年金现值系数: {pv_factor:.2f}\n"
            result_text += f"电价: {electricity_price:.2f} 元/kWh | 运维费用: {maintenance_rate:.2f} 元/m·年\n\n"

            # 技术校验结果
            result_text += f"【技术校验结果】\n"
            result_text += f"{'-'*110}\n"
            result_text += f"{'校验项目':<12}{'计算截面':<14}{'校验依据':<36}{'状态':<10}\n"
            result_text += f"{'-'*110}\n"
            
            # 热稳定校验
            thermal_status = "✅ 通过" if s_min_thermal <= max(sections) else "⚠️ 超限"
            result_text += f"{'热稳定校验':<12}{s_min_thermal:<14.2f}mm² {'C={:.0f}, Ik={:.1f}kA'.format(c_factor, ik_kA):<36}{thermal_status:<10}\n"
            
            # 载流量校验
            ampacity = self.get_current_capacity(s_min_ampacity, voltage, is_copper, temp, install_method, soil_resistivity)
            ampacity_status = "✅ 通过" if ampacity >= imax else "⚠️ 不足"
            result_text += f"{'载流量校验':<12}{s_min_ampacity:<14}mm² {'I_n={:.0f}A ≥ I_max={:.1f}A'.format(ampacity, imax):<36}{ampacity_status:<10}\n"
            
            # 电压降校验
            vd = self.calculate_voltage_drop(s_min_voltage, voltage, is_copper, imax, length_km, cosphi)
            voltage_status = "✅ 通过" if vd <= allowed_voltage_drop else "⚠️ 超标"
            result_text += f"{'电压降校验':<12}{s_min_voltage:<14}mm² {'ΔU={:.2f}% ≤ {:.1f}%'.format(vd, allowed_voltage_drop):<36}{voltage_status:<10}\n"
            
            result_text += f"{'-'*110}\n"
            result_text += f"{'最小要求截面':<12}{s_min_required:<14}mm² {'max(热稳定,载流量,电压降)':<36}{'--':<10}\n"
            result_text += f"{'经济截面':<12}{s_eco:<14.2f}mm² {'Jec={:.3f} A/mm² (公式计算)'.format(jec):<36}{'--':<10}\n"
            result_text += f"\n【经济电流密度计算】\n"
            result_text += f"  公式: Jec = √(1000×a / (3×ρ×τ×C2×N))\n"
            result_text += f"  其中: a=电缆成本系数, ρ=电阻率, τ={tau:.0f}h, C2={electricity_price}元/kWh, N={pv_factor:.2f}\n"
            result_text += f"  说明: 按GB50217附录B公式，根据实际电价、铜价、贴现率动态计算\n\n"

            # 选型逻辑说明
            result_text += f"【选型逻辑】\n"
            result_text += f"{'-'*110}\n"
            result_text += f"✓ 最小要求截面: {s_min_required}mm² (max(热稳定,载流量,电压降))\n"
            result_text += f"✓ 经济截面: {s_eco:.1f}mm² (Jec={jec:.3f} A/mm²)\n"
            if s_eco >= s_min_required:
                result_text += f"✓ 经济截面 ≥ 最小要求截面 → 经济选型可行\n"
            else:
                result_text += f"⚠ 经济截面 < 最小要求截面 → 需按技术条件选型\n"
            result_text += f"✓ 候选方案从最小要求截面开始，展示LCC变化趋势\n"
            result_text += f"✓ 所有候选截面均满足：热稳定 + 载流量 + 电压降 三项约束\n\n"

            # 经济对比表
            result_text += f"【经济选型对比】\n"
            result_text += f"{'-'*120}\n"
            # 表头 - 添加技术校验列
            result_text += f"{'截面(mm²)':<12}{'载流量(A)':<12}{'电压降(%)':<12}{'单价(元/m)':<14}{'初始投资(元)':<16}{'年损耗(元)':<14}{'总现值(元)':<16}{'技术校验':<8}\n"
            result_text += f"{'-'*120}\n"

            best_section = None
            min_total_cost = float('inf')
            best_is_valid = False  # 追踪最优方案是否满足技术条件

            for sec in candidate_sections:
                investment = self.calculate_initial_investment(
                    sec, length, voltage, is_copper, cu_price, al_price, channel_cost
                )
                initial_cost = investment['total']
                
                r = self.get_resistance(sec, voltage, is_copper)
                # 三相线路功率损耗: ΔP = 3 × I² × R × L (W)
                # 转换为kW: ΔP(kW) = ΔP(W) / 1000
                power_loss_w = 3 * imax**2 * r * length_km
                power_loss_kw = power_loss_w / 1000
                annual_loss = power_loss_kw * tau * electricity_price
                
                loss_pv = annual_loss * pv_factor
                maint_pv = maintenance_rate * length * pv_factor
                total_cost_pv = initial_cost + loss_pv + maint_pv

                capacity = self.get_current_capacity(sec, voltage, is_copper, temp, install_method, soil_resistivity)
                voltage_drop = self.calculate_voltage_drop(sec, voltage, is_copper, imax, length_km, cosphi)
                
                # 【双重保险】再次校验技术条件
                tech_thermal = sec >= s_min_thermal
                tech_ampacity = capacity >= imax
                tech_voltage = voltage_drop <= allowed_voltage_drop
                is_valid = tech_thermal and tech_ampacity and tech_voltage

                # 数据行 - 添加技术校验列
                valid_mark = "✅" if is_valid else "⚠️"
                line = f"{sec:<12}{capacity:<12.0f}{voltage_drop:<12.2f}{investment['cable_price']:<14.1f}{initial_cost:<16,.0f}{annual_loss:<14,.0f}{total_cost_pv:<16,.0f}{valid_mark:<8}\n"
                result_text += line

                # 只有满足技术条件的截面才能成为最优选择
                if is_valid and total_cost_pv < min_total_cost:
                    min_total_cost = total_cost_pv
                    best_section = sec
                    best_investment = investment
                    best_annual_loss = annual_loss
                    best_capacity = capacity
                    best_voltage_drop = voltage_drop
                    best_is_valid = True

            # 如果没有满足条件的截面（理论上不应该发生），取最小要求截面
            if best_section is None or not best_is_valid:
                # 找到满足条件的最小截面
                for sec in valid_sections:
                    capacity = self.get_current_capacity(sec, voltage, is_copper, temp, install_method, soil_resistivity)
                    voltage_drop = self.calculate_voltage_drop(sec, voltage, is_copper, imax, length_km, cosphi)
                    if sec >= s_min_thermal and capacity >= imax and voltage_drop <= allowed_voltage_drop:
                        best_section = sec
                        best_investment = self.calculate_initial_investment(
                            sec, length, voltage, is_copper, cu_price, al_price, channel_cost
                        )
                        best_capacity = capacity
                        best_voltage_drop = voltage_drop
                        r = self.get_resistance(sec, voltage, is_copper)
                        power_loss_kw = 3 * imax**2 * r * length_km / 1000
                        best_annual_loss = power_loss_kw * tau * electricity_price
                        break

            result_text += f"{'-'*110}\n"
            
            # 推荐结果
            result_text += f"\n【推荐结果】\n"
            result_text += f"{'-'*110}\n"
            result_text += f"✅ 推荐截面: {best_section} mm²\n"
            result_text += f"✅ 电缆型号: {cable_model}-{voltage}kV-{cores}×{best_section}\n\n"
            
            result_text += f"【初始投资明细】\n"
            result_text += f"{'-'*110}\n"
            result_text += f"  电缆价格: {best_investment['cable_price']:.1f} 元/m\n"
            result_text += f"  电缆成本: {best_investment['cable_cost']:,.0f} 元\n"
            result_text += f"  通道费用: {best_investment['channel_cost']:,.0f} 元\n"
            result_text += f"  附件费用: {best_investment['attachment_cost']:,.0f} 元 ({'10kV按10%' if voltage == 10 else '1kV按2%'})\n"
            result_text += f"  其他费用: {best_investment['other_cost']:,.0f} 元 (按8%计算)\n"
            result_text += f"  {'-'*70}\n"
            result_text += f"  初始投资合计: {best_investment['total']:,.0f} 元\n\n"
            
            result_text += f"【全生命周期成本】\n"
            result_text += f"{'-'*110}\n"
            result_text += f"  年损耗费用: {best_annual_loss:,.0f} 元/年\n"
            result_text += f"  年运维费用: {maintenance_rate * length:,.0f} 元/年\n"
            result_text += f"  损耗费用现值: {best_annual_loss * pv_factor:,.0f} 元\n"
            result_text += f"  运维费用现值: {maintenance_rate * length * pv_factor:,.0f} 元\n"
            result_text += f"  {'-'*70}\n"
            result_text += f"  总费用现值: {min_total_cost:,.0f} 元\n\n"

            # 技术校验确认
            result_text += f"【技术校验确认】\n"
            result_text += f"{'-'*110}\n"
            result_text += f"  载流量: {best_capacity:.0f}A {'✅' if best_capacity >= imax else '⚠️'} (需求{imax:.1f}A)\n"
            result_text += f"  电压降: {best_voltage_drop:.2f}% {'✅' if best_voltage_drop <= allowed_voltage_drop else '⚠️'} (限值{allowed_voltage_drop}%)\n"
            result_text += f"  热稳定: {'✅' if best_section * 1.0 >= s_min_thermal else '⚠️'} (最小{s_min_thermal:.1f}mm²)\n\n"

            result_text += f"【计算依据】\n"
            result_text += f"{'-'*110}\n"
            result_text += f"1. GB50217-2018《电力工程电缆设计标准》\n"
            result_text += f"2. 《工业与民用配电设计手册》第四版\n"
            result_text += f"3. 热稳定系数: 铜C=137, 铝C=93\n"
            result_text += f"4. XLPE绝缘最高温度: 90℃\n"
            result_text += f"5. 载流量基准: 土壤直埋, 25℃, 热阻2.0K·m/W\n"
            result_text += f"6. 经济电流密度: 按GB50217附录B公式动态计算\n"

            self.result_text.setText(result_text)

        except Exception as e:
            QMessageBox.critical(self, "计算错误", f"发生计算错误:\n{str(e)}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CableCalculator()
    window.show()
    sys.exit(app.exec_())
