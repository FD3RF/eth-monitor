# ai_audit.py
"""
AI 审计模块 - 基于市场数据进行智能分析
确保 AI 分析与其他指标逻辑一致，避免矛盾
"""
import time
import numpy as np
from typing import Tuple, Optional, Dict
from config import AI_FAIL_COOLDOWN, AI_MAX_FAIL_COUNT


class AIAuditor:
    """AI审计器"""
    
    def __init__(self):
        self.fail_count = 0
        self.last_fail_time = 0
        self._last_audit_time = 0
        self._cached_score = None
        self._cached_report = None
    
    def audit(self, market_data: Dict = None, indicator_scores: Dict = None) -> Tuple[Optional[float], str]:
        """
        AI审计分析
        :param market_data: 市场数据
        :param indicator_scores: 其他指标评分
        :return: (评分, 报告)
        """
        now = time.time()
        
        # 缓存检查
        if self._cached_score is not None and (now - self._last_audit_time) < 5:
            return self._cached_score, self._cached_report
        
        # 熔断检查
        if self.fail_count >= AI_MAX_FAIL_COUNT:
            if now - self.last_fail_time < AI_FAIL_COOLDOWN:
                return None, "AI服务熔断中"
            self.fail_count = 0
        
        # 模拟失败（5%概率）
        if np.random.random() < 0.05:
            self.fail_count += 1
            self.last_fail_time = now
            return None, "AI服务不可用"
        
        # 获取市场数据
        if market_data is None:
            from indicators import get_market_summary
            market_data = get_market_summary()
        
        # 分析市场
        score, report = self._analyze_market(market_data, indicator_scores)
        
        # 缓存
        self._cached_score = score
        self._cached_report = report
        self._last_audit_time = now
        
        return score, report
    
    def _analyze_market(self, market_data: Dict, indicator_scores: Dict = None) -> Tuple[float, str]:
        """分析市场数据"""
        score = 0.0
        points = []
        
        trend = market_data.get('trend', 0)
        rsi = market_data.get('rsi', 50)
        volume_ratio = market_data.get('volume_ratio', 1.0)
        price = market_data.get('price', 3500)
        support = market_data.get('support', 3400)
        resistance = market_data.get('resistance', 3600)
        volatility = market_data.get('volatility', 0.02)
        
        # 1. 趋势分析 (30%)
        if trend > 0:
            score += 30
            points.append(f"趋势: 上升趋势，偏多")
        elif trend < 0:
            score -= 30
            points.append(f"趋势: 下降趋势，偏空")
        else:
            points.append(f"趋势: 震荡，方向不明")
        
        # 2. RSI分析 (20%)
        if rsi > 70:
            score -= 15
            points.append(f"RSI: {rsi:.0f}超买，回调风险")
        elif rsi < 30:
            score += 15
            points.append(f"RSI: {rsi:.0f}超卖，反弹机会")
        else:
            score += (rsi - 50) * 0.3
            points.append(f"RSI: {rsi:.0f}正常区间")
        
        # 3. 成交量分析 (20%)
        if volume_ratio > 1.5:
            if trend > 0:
                score += 20
                points.append(f"成交量: 放量上涨，多头强")
            elif trend < 0:
                score -= 20
                points.append(f"成交量: 放量下跌，空头强")
            else:
                points.append(f"成交量: 放量震荡")
        else:
            points.append(f"成交量: 平稳")
        
        # 4. 位置分析 (15%)
        position = (price - support) / (resistance - support) if resistance != support else 0.5
        if position > 0.7:
            score -= 10
            points.append(f"位置: 接近压力位")
        elif position < 0.3:
            score += 10
            points.append(f"位置: 接近支撑位")
        else:
            points.append(f"位置: 区间中部")
        
        # 5. 波动率 (15%)
        if volatility > 0.03:
            score *= 0.85
            points.append(f"波动率: 高波动")
        else:
            points.append(f"波动率: 正常")
        
        # 6. 与其他指标交叉验证
        if indicator_scores:
            other_avg = sum(indicator_scores.values()) / len(indicator_scores)
            
            # 确保AI与其他指标方向一致
            if (score > 0 and other_avg > 0) or (score < 0 and other_avg < 0):
                score = score * 1.1  # 同向增强
                points.append(f"验证: 与其他指标一致")
            elif abs(score - other_avg) > 30:
                score = score * 0.6  # 分歧减弱
                points.append(f"验证: 与其他指标分歧")
        
        score = max(-100, min(100, score))
        
        # 生成方向建议
        if score > 30:
            direction = "做多"
            confidence = "高" if score > 60 else "中"
        elif score < -30:
            direction = "做空"
            confidence = "高" if score < -60 else "中"
        else:
            direction = "观望"
            confidence = "低"
        
        report = f"""### AI审计报告
{chr(10).join(['- ' + p for p in points])}

**评分**: {score:.1f}
**方向**: {direction}
**强度**: {confidence}"""
        
        return round(score, 2), report
    
    def quick_score(self, market_data: Dict = None, indicator_scores: Dict = None) -> float:
        """快速获取AI评分"""
        score, _ = self.audit(market_data, indicator_scores)
        return score if score is not None else 0


# 全局实例
auditor = AIAuditor()
