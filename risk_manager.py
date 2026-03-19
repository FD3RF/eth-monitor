# risk_manager.py
"""
风险管理模块 - 仓位计算、止损止盈设置
确保风险可控，避免过度杠杆
"""
from typing import Tuple
from config import RISK_PER_TRADE, MAX_POSITION_RATIO, REWARD_RISK_RATIO


def calculate_position_size(
    account_balance: float,
    entry_price: float,
    stop_loss_price: float,
    signal_strength: float
) -> float:
    """
    计算仓位大小
    :param account_balance: 账户余额（USDT）
    :param entry_price: 入场价格
    :param stop_loss_price: 止损价格
    :param signal_strength: 信号强度（0到1之间的系数）
    :return: 建议仓位（USDT）
    """
    if account_balance <= 0 or entry_price <= 0:
        return 0
    
    # 计算单笔风险金额
    risk_amount = account_balance * RISK_PER_TRADE
    
    # 计算止损百分比
    price_risk = abs(entry_price - stop_loss_price)
    if price_risk == 0:
        return 0
    
    stop_loss_pct = price_risk / entry_price
    
    # 基础仓位 = 风险金额 / 止损百分比
    base_position = risk_amount / stop_loss_pct
    
    # 根据信号强度调整仓位（信号越强，仓位越大，但不超过上限）
    # 信号强度 0.3 -> 仓位 70%, 信号强度 1.0 -> 仓位 100%
    strength_factor = 0.7 + signal_strength * 0.3
    adjusted_position = base_position * strength_factor
    
    # 限制最大仓位
    max_position = account_balance * MAX_POSITION_RATIO
    adjusted_position = min(adjusted_position, max_position)
    
    return round(adjusted_position, 2)


def calculate_take_profit(
    entry_price: float,
    stop_loss_price: float,
    direction: str,
    risk_reward_ratio: float = REWARD_RISK_RATIO
) -> float:
    """
    计算止盈价格
    :param entry_price: 入场价格
    :param stop_loss_price: 止损价格
    :param direction: 'long' 或 'short'
    :param risk_reward_ratio: 风险收益比
    :return: 止盈价格
    """
    risk = abs(entry_price - stop_loss_price)
    reward = risk * risk_reward_ratio
    
    if direction == 'long':
        take_profit = entry_price + reward
    else:
        take_profit = entry_price - reward
    
    return round(take_profit, 2)


def calculate_stop_loss(
    entry_price: float,
    support: float,
    resistance: float,
    direction: str,
    buffer_pct: float = 0.005
) -> float:
    """
    计算止损价格
    :param entry_price: 入场价格
    :param support: 支撑位
    :param resistance: 压力位
    :param direction: 'long' 或 'short'
    :param buffer_pct: 缓冲百分比（避免被假突破止损）
    :return: 止损价格
    """
    if direction == 'long':
        # 做多止损设在支撑位下方
        stop_loss = support * (1 - buffer_pct)
        # 确保止损在入场价下方
        if stop_loss >= entry_price:
            stop_loss = entry_price * (1 - 0.02)  # 默认2%止损
    else:
        # 做空止损设在压力位上方
        stop_loss = resistance * (1 + buffer_pct)
        # 确保止损在入场价上方
        if stop_loss <= entry_price:
            stop_loss = entry_price * (1 + 0.02)  # 默认2%止损
    
    return round(stop_loss, 2)


def calculate_entry_price(
    current_price: float,
    direction: str,
    slippage_pct: float = 0.001
) -> float:
    """
    计算入场价格
    :param current_price: 当前价格
    :param direction: 'long' 或 'short'
    :param slippage_pct: 滑点百分比
    :return: 入场价格
    """
    if direction == 'long':
        # 做多时，考虑买入滑点
        entry = current_price * (1 + slippage_pct)
    else:
        # 做空时，考虑卖出滑点
        entry = current_price * (1 - slippage_pct)
    
    return round(entry, 2)


def validate_trade_plan(
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    direction: str
) -> Tuple[bool, str]:
    """
    验证交易计划是否合理
    :return: (是否有效, 错误信息)
    """
    if direction == 'long':
        if stop_loss >= entry_price:
            return False, "做多止损必须在入场价下方"
        if take_profit <= entry_price:
            return False, "做多止盈必须在入场价上方"
    else:
        if stop_loss <= entry_price:
            return False, "做空止损必须在入场价上方"
        if take_profit >= entry_price:
            return False, "做空止盈必须在入场价下方"
    
    # 验证风险收益比
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    if risk == 0:
        return False, "止损距离为0"
    
    rr_ratio = reward / risk
    if rr_ratio < 1.5:
        return False, f"风险收益比不足（{rr_ratio:.1f}），建议至少1.5"
    
    return True, "验证通过"


def calculate_risk_metrics(
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    position_size: float
) -> dict:
    """
    计算风险指标
    """
    risk = abs(entry_price - stop_loss) * position_size / entry_price
    reward = abs(take_profit - entry_price) * position_size / entry_price
    
    return {
        'risk_amount': round(risk, 2),
        'reward_amount': round(reward, 2),
        'risk_reward_ratio': round(reward / risk, 2) if risk > 0 else 0,
        'risk_pct': round(abs(entry_price - stop_loss) / entry_price * 100, 2)
    }
