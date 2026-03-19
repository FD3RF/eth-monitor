# trading_engine.py
"""
统一决策引擎 - 综合各指标生成交易决策
确保多空逻辑清晰，指标不冲突，交易计划合理
"""
import numpy as np
from typing import Dict, Tuple, Optional
from config import WEIGHTS, SIGNAL_THRESHOLD_STRONG, SIGNAL_THRESHOLD_WEAK, CONFLICT_THRESHOLD
from indicators import (
    calculate_volume_price, calculate_multi_resonance,
    calculate_market_structure, calculate_lstm_prediction,
    calculate_money_flow, get_support_resistance, get_market_summary
)
from ai_audit import auditor
from risk_manager import (
    calculate_position_size, calculate_take_profit,
    calculate_stop_loss, calculate_entry_price, validate_trade_plan
)


class TradingDecisionEngine:
    def __init__(self):
        self.weights = WEIGHTS
        self._last_plan = None
    
    def calculate_all_indicators(self) -> Dict[str, float]:
        """
        计算所有指标评分，统一归一化到 -100 到 100
        """
        scores = {
            'volume_price': calculate_volume_price(),
            'multi_resonance': calculate_multi_resonance(),
            'market_structure': calculate_market_structure(),
            'lstm_prediction': calculate_lstm_prediction(),
            'money_flow': calculate_money_flow()
        }
        return scores
    
    def calculate_composite_score(self, indicator_scores: Dict[str, float] = None) -> Tuple[float, Dict, str, float]:
        """
        计算综合评分和方向
        :return: (综合评分, 各指标得分, 方向, 信号强度)
        """
        # 获取指标评分
        if indicator_scores is None:
            indicator_scores = self.calculate_all_indicators()
        
        # 获取 AI 评分
        market_summary = get_market_summary()
        ai_score = auditor.quick_score(market_summary)
        
        # 合并所有评分
        all_scores = {**indicator_scores, 'ai_score': ai_score}
        
        # 计算加权综合评分（统一范围 -100 到 100）
        weighted_sum = 0.0
        total_weight = 0.0
        
        for name, score in all_scores.items():
            weight = self.weights.get(name, 0.1)
            weighted_sum += score * weight
            total_weight += weight
        
        composite = weighted_sum / total_weight if total_weight > 0 else 0
        composite = round(composite, 2)
        
        # 计算归一化的信号强度 (0-1)
        signal_strength = min(abs(composite) / 100, 1.0)
        
        # 确定方向
        if composite > 20:  # 阈值：20分以上才做多
            direction = 'long'
        elif composite < -20:  # 阈值：-20分以下才做空
            direction = 'short'
        else:
            direction = 'neutral'
            signal_strength = 0
        
        return composite, all_scores, direction, signal_strength
    
    def check_signal_conflict(self, scores: Dict[str, float]) -> Tuple[bool, str]:
        """
        智能检查信号冲突
        :return: (是否存在冲突, 冲突描述)
        """
        # 分离多头和空头信号
        long_signals = {k: v for k, v in scores.items() if v > 10}
        short_signals = {k: v for k, v in scores.items() if v < -10}
        
        # 计算多头和空头的加权强度
        long_strength = sum(v * self.weights.get(k, 0.1) for k, v in long_signals.items())
        short_strength = sum(abs(v) * self.weights.get(k, 0.1) for k, v in short_signals.items())
        
        total_strength = long_strength + short_strength
        
        if total_strength == 0:
            return False, ""
        
        # 计算冲突比例
        conflict_ratio = min(long_strength, short_strength) / total_strength
        
        # 冲突检测逻辑
        if conflict_ratio > CONFLICT_THRESHOLD:
            conflict_desc = f"信号冲突：多头强度 {long_strength:.1f} vs 空头强度 {short_strength:.1f}"
            return True, conflict_desc
        
        # 检查是否有强对立指标
        strong_long = [k for k, v in scores.items() if v > 50]
        strong_short = [k for k, v in scores.items() if v < -50]
        
        if strong_long and strong_short:
            conflict_desc = f"强信号对立：多头[{', '.join(strong_long)}] vs 空头[{', '.join(strong_short)}]"
            return True, conflict_desc
        
        return False, ""
    
    def get_signal_quality(self, composite: float, signal_strength: float, has_conflict: bool) -> str:
        """
        评估信号质量
        """
        if has_conflict:
            return "冲突"
        
        if signal_strength >= 0.7:
            return "强"
        elif signal_strength >= 0.4:
            return "中"
        elif signal_strength >= 0.2:
            return "弱"
        else:
            return "无"
    
    def generate_trading_plan(self, account_balance: float) -> Dict:
        """
        生成完整交易计划
        """
        # 1. 计算指标和综合评分
        indicator_scores = self.calculate_all_indicators()
        composite, all_scores, direction, signal_strength = self.calculate_composite_score(indicator_scores)
        
        # 2. 检查信号冲突
        has_conflict, conflict_desc = self.check_signal_conflict(all_scores)
        
        # 3. 获取市场数据
        market_summary = get_market_summary()
        current_price = market_summary['price']
        support = market_summary['support']
        resistance = market_summary['resistance']
        
        # 4. 构建基础计划
        plan = {
            'direction': direction,
            'composite_score': composite,
            'signal_strength': signal_strength,
            'scores': all_scores,
            'has_conflict': has_conflict,
            'conflict_desc': conflict_desc,
            'signal_quality': self.get_signal_quality(composite, signal_strength, has_conflict),
            'current_price': current_price,
            'support': support,
            'resistance': resistance,
            'market_summary': market_summary,
            'tradeable': False,  # 默认不可交易
            'reason': ''
        }
        
        # 5. 检查是否可交易
        if direction == 'neutral':
            plan['reason'] = '无明确方向信号'
            return plan
        
        if has_conflict:
            plan['reason'] = f'信号冲突：{conflict_desc}'
            return plan
        
        if signal_strength < 0.2:
            plan['reason'] = '信号强度不足'
            return plan
        
        # 6. 生成交易参数
        entry_price = calculate_entry_price(current_price, direction)
        stop_loss = calculate_stop_loss(entry_price, support, resistance, direction)
        take_profit = calculate_take_profit(entry_price, stop_loss, direction)
        position_size = calculate_position_size(account_balance, entry_price, stop_loss, signal_strength)
        
        # 7. 验证交易计划
        is_valid, validation_msg = validate_trade_plan(entry_price, stop_loss, take_profit, direction)
        
        if not is_valid:
            plan['reason'] = f'计划验证失败：{validation_msg}'
            return plan
        
        # 8. 完成可交易计划
        plan.update({
            'entry': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'position_size': position_size,
            'tradeable': True,
            'reason': '计划生成成功'
        })
        
        self._last_plan = plan
        return plan
    
    def get_trade_recommendation(self, plan: Dict) -> str:
        """
        生成交易建议文本
        """
        if not plan.get('tradeable'):
            return f"**不建议交易**：{plan.get('reason', '无有效计划')}"
        
        direction_text = "做多" if plan['direction'] == 'long' else "做空"
        quality_text = plan.get('signal_quality', '未知')
        
        recommendation = f"""
**交易建议**: {direction_text}
**信号质量**: {quality_text}
**综合评分**: {plan['composite_score']:.1f}
**信号强度**: {plan['signal_strength']*100:.0f}%

**入场价格**: ${plan['entry']:,.2f}
**止损价格**: ${plan['stop_loss']:,.2f}
**止盈价格**: ${plan['take_profit']:,.2f}
**建议仓位**: ${plan['position_size']:,.2f} USDT
"""
        return recommendation


# 全局引擎实例
engine = TradingDecisionEngine()
