# import numpy as np
# from scipy.optimize import root_scalar

# def reverse_dcf_audit(current_price: float, fcf_per_share: float, wacc: float, g_terminal: float, years: int = 5):
#     """
#     通过逆向 DCF 反推市场隐含的短期年化复合增长率 (Implied CAGR)
    
#     参数:
#     current_price: 当前股票现价
#     fcf_per_share: 经审计的每股自由现金流 (Adj. FCF / Shares Outstanding)
#     wacc: 加权平均资本成本 (作为折现率)
#     g_terminal: 永续增长率 (通常锚定长期通胀率 2%-3%)
#     years: 短期高速增长预测期 (默认 5 年)
#     """
#     if fcf_per_share <= 0:
#         return "审计失败: FCF 为负或零，DCF 基础数学逻辑不成立。"
        
#     def objective_function(g):
#         # 1. 计算前 n 年的 FCF 现值总和 (PV of FCF)
#         cash_flows = [fcf_per_share * (1 + g)**t for t in range(1, years + 1)]
#         pv_fcf = sum(cf / (1 + wacc)**t for t, cf in enumerate(cash_flows, 1))
        
#         # 2. 计算终值 (Terminal Value) 及其现值
#         # 戈登增长模型 (Gordon Growth Model)
#         terminal_value = (cash_flows[-1] * (1 + g_terminal)) / (wacc - g_terminal)
#         pv_tv = terminal_value / (1 + wacc)**years
        
#         # 3. 目标等式：计算出的内在价值 减去 当前股价，寻根算法目标是使差值为 0
#         return (pv_fcf + pv_tv) - current_price

#     try:
#         # 使用 Brent 算法在 -50% 到 200% 的增长率区间内寻找根
#         result = root_scalar(objective_function, bracket=[-0.5, 2.0], method='brentq')
#         if result.converged:
#             implied_g = result.root
#             return f"市场隐含的短期期望增长率 (Implied Growth Rate) 为: {implied_g:.2%}"
#         else:
#             return "算法未收敛，请检查输入参数是否合理。"
#     except ValueError:
#         return "无解：市场定价极度非理性，或 WACC 设置低于永续增长率。"

# # 示例：复现可口可乐 (KO) 的逆向推演
# print("--- 可口可乐 (KO) 审计 ---")
# print(reverse_dcf_audit(current_price=77.34, fcf_per_share=2.64, wacc=0.075, g_terminal=0.025))


import numpy as np
from scipy.optimize import root_scalar

def tech_reverse_dcf(price: float, fcf_per_share: float, wacc: float, g_term: float, years: int):
    """
    针对高科技成长股的逆向 DCF 测算引擎
    """
    if fcf_per_share <= 0:
        return "无法测算: FCF为负"
        
    def objective_function(g):
        # 阶段 1: 预测期内现金流现值
        cash_flows = [fcf_per_share * (1 + g)**t for t in range(1, years + 1)]
        pv_fcf = sum(cf / (1 + wacc)**t for t, cf in enumerate(cash_flows, 1))
        
        # 阶段 2: 永续期终值现值 (Gordon Growth)
        terminal_value = (cash_flows[-1] * (1 + g_term)) / (wacc - g_term)
        pv_tv = terminal_value / (1 + wacc)**years
        
        # 寻找让 (内在价值 - 现价) 为 0 的增长率 g
        return (pv_fcf + pv_tv) - price

    try:
        # 使用 Brentq 寻根，范围设定为 -50% 到 100%
        result = root_scalar(objective_function, bracket=[-0.5, 1.0], method='brentq')
        if result.converged:
            return result.root
        else:
            return None
    except ValueError:
        return "模型无解: 现价极度脱离数学常识或折现率过低"

# --- 英伟达 (NVDA) 实时数据锚定 ---
# 现价 (2026/03)
current_price = 180.20
# FY2026 全年 FCF / 245亿流通股
fcf0 = 3.96
# 折现率 (4.28% 美债 + 高Beta风险溢价)
wacc = 0.115 
# 永续增长
g_terminal = 0.025 

implied_g_10yr = tech_reverse_dcf(current_price, fcf0, wacc, g_terminal, 10)

print(f"--- 宏观/基本面风控审计 ---")
print(f"锚定现价: ${current_price} | WACC: {wacc:.1%}")
print(f"市场隐含的未来 10 年 FCF 年化复利增速 (Implied CAGR): {implied_g_10yr:.2%}")
print(f"第 10 年要求绝对产出规模: ${(fcf0 * (1+implied_g_10yr)**10) * 24.5:.2f} 亿美元")