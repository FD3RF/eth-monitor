# trading_engine.py
"""
统一决策引擎 - 综合各指标生成交易决策
确保多空逻辑清晰，指标不冲突，交易计划合理
"""
import numpy as np
from typing import Dict, Tuple, Optional
from config import WEIGHTS, CONFLICT_THRESHOLD
from indicators import (
    calculate_volume_price, calculate_multi_resonance,
    calculate_market_structure, calculate_lstm_prediction,
    calculate_money_flow, get_support_resistance, get_market_summary, market_data
)
from ai_audit import auditor
from risk_manager import (
    calculate_position_size, calculate_take_profit,
    calculate_stop_loss, calculate_entry_price, validate_trade_plan
)


class TradingDecisionEngine:
    """统一交易决策引擎"""
    
    def __init__(self):
        self.weights = WEIGHTS
        self._last_plan = None
        self._last_scores = None
    
    def calculate_all_indicators(self) -> Dict[str, float]:
        """
        计算所有指标评分
        确保所有指标基于同一市场数据快照
        """
        market_data.refresh(force=False)
        
        scores = {
            'volume_price': calculate_volume_price(),
            'multi_resonance': calculate_multi_resonance(),
            'market_structure': calculate_market_structure(),
            'lstm_prediction': calculate_lstm_prediction(),
            'money_flow': calculate_money_flow()
        }
        
        self._last_scores = scores
        return scores
    
    def calculate_composite_score(self, indicator_scores: Dict[str, float] = None) -> Tuple[float, Dict, str, float]:
        """
        计算综合评分和方向
        :return: (综合评分, 各指标得分, 方向, 信号强度)
        """
        if indicator_scores is None:
            indicator_scores = self.calculate_all_indicators()
        
        # 获取 AI 评分
        market_summary = get_market_summary()
        ai_score = auditor.quick_score(market_summary, indicator_scores)
        
        # 合并所有评分
        all_scores = {**indicator_scores, 'ai_score': ai_score}
        
        # 计算加权综合评分
        weighted_sum = sum(score * self.weights.get(name, 0.1) for name, score in all_scores.items())
        total_weight = sum(self.weights.get(name, 0.1) for name in all_scores)
        
        composite = weighted_sum / total_weight if total_weight > 0 else 0
        composite = round(composite, 2)
        
        # 信号强度
        signal_strength = min(abs(composite) / 100, 1.0)
        
        # 确定方向（阈值25分）
        if composite > 25:
            direction = 'long'
        elif composite < -25:
            direction = 'short'
        else:
            direction = 'neutral'
            signal_strength = 0
        
        return composite, all_scores, direction, signal_strength
    
    def check_signal_conflict(self, scores: Dict[str, float]) -> Tuple[bool, str, float]:
        """
        检查信号冲突
        :return: (是否冲突, 描述, 严重程度)
        """
        # 计算多头空头加权强度
        long_strength = sum(abs(v) * self.weights.get(k, 0.1) for k, v in scores.items() if v > 5)
        short_strength = sum(abs(v) * self.weights.get(k, 0.1) for k, v in scores.items() if v < -5)
        
        total = long_strength + short_strength
        if total == 0:
            return False, "", 0.0
        
        conflict_ratio = min(long_strength, short_strength) / total
        
        # 冲突判断
        if conflict_ratio > CONFLICT_THRESHOLD:
            desc = f"多头{long_strength:.1f} vs 空头{short_strength:.1f}"
            return True, desc, conflict_ratio
        
        # 强信号对立检测
        strong_long = [k for k, v in scores.items() if v > 60]
        strong_short = [k for k, v in scores.items() if v < -60]
        
        if strong_long and strong_short:
            return True, f"强信号对立: {strong_long} vs {strong_short}", 0.8
        
        return False, "", conflict_ratio
    
    def get_signal_quality(self, signal_strength: float, has_conflict: bool, conflict_severity: float) -> str:
        """评估信号质量"""
        if has_conflict:
            return "严重冲突" if conflict_severity > 0.5 else "轻度冲突"
        
        if signal_strength >= 0.7:
            return "强"
        elif signal_strength >= 0.4:
            return "中"
        elif signal_strength >= 0.25:
            return "弱"
        return "无"
    
    def generate_trading_plan(self, account_balance: float) -> Dict:
        """生成交易计划"""
        # 1. 计算指标
        indicator_scores = self.calculate_all_indicators()
        composite, all_scores, direction, signal_strength = self.calculate_composite_score(indicator_scores)
        
        # 2. 检查冲突
        has_conflict, conflict_desc, conflict_severity = self.check_signal_conflict(all_scores)
        
        # 3. 获取市场数据
        market_summary = get_market_summary()
        current_price = market_summary['price']
        support = market_summary['support']
        resistance = market_summary['resistance']
        
        # 4. 计算一致性
        long_count = sum(1 for v in all_scores.values() if v > 15)
        short_count = sum(1 for v in all_scores.values() if v < -15)
        consensus_ratio = max(long_count, short_count) / len(all_scores)
        
        # 5. 构建计划
        plan = {
            'direction': direction,
            'composite_score': composite,
            'signal_strength': signal_strength,
            'scores': all_scores,
            'has_conflict': has_conflict,
            'conflict_desc': conflict_desc,
            'conflict_severity': conflict_severity,
            'signal_quality': self.get_signal_quality(signal_strength, has_conflict, conflict_severity),
            'current_price': current_price,
            'support': support,
            'resistance': resistance,
            'market_summary': market_summary,
            'tradeable': False,
            'reason': '',
            'consensus': {
                'long_count': long_count,
                'short_count': short_count,
                'ratio': consensus_ratio
            }
        }
        
        # 6. 验证条件
        errors = []
        
        if direction == 'neutral':
            errors.append('无明确方向')
        
        if has_conflict and conflict_severity > 0.3:
            errors.append(f'信号冲突: {conflict_desc}')
        
        if signal_strength < 0.25:
            errors.append(f'强度不足({signal_strength:.0%})')
        
        if consensus_ratio < 0.5:
            errors.append(f'一致性低({consensus_ratio:.0%})')
        
        # AI方向一致性验证
        ai_score = all_scores.get('ai_score', 0)
        if direction == 'long' and ai_score < -20:
            errors.append(f'AI评分矛盾({ai_score:.0f})')
        elif direction == 'short' and ai_score > 20:
            errors.append(f'AI评分矛盾({ai_score:.0f})')
        
        if errors:
            plan['reason'] = ' | '.join(errors)
            return plan
        
        # 7. 生成交易参数
        entry_price = calculate_entry_price(current_price, direction)
        stop_loss = calculate_stop_loss(entry_price, support, resistance, direction)
        take_profit = calculate_take_profit(entry_price, stop_loss, direction)
        position_size = calculate_position_size(account_balance, entry_price, stop_loss, signal_strength)
        
        # 8. 验证计划
        is_valid, msg = validate_trade_plan(entry_price, stop_loss, take_profit, direction)
        if not is_valid:
            plan['reason'] = f'验证失败: {msg}'
            return plan
        
        # 9. 风险合理性检查
        risk_pct = abs(entry_price - stop_loss) / entry_price * 100
        if not (0.5 <= risk_pct <= 5):
            plan['reason'] = f'止损不合理({risk_pct:.1f}%)'
            return plan
        
        # 10. 完成计划
        plan.update({
            'entry': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'position_size': position_size,
            'risk_pct': risk_pct,
            'tradeable': True,
            'reason': '验证通过'
        })
        
        self._last_plan = plan
        return plan


# 全局引擎实例
engine = TradingDecisionEngine()
