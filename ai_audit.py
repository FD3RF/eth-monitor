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
    def __init__(self):
        self.fail_count = 0
        self.last_fail_time = 0
        self._last_audit_time = 0
        self._cached_score = None
        self._cached_report = None
    
    def audit(self, market_data: Dict = None, indicator_scores: Dict = None) -> Tuple[Optional[float], str]:
        """
        AI 审计分析
        :param market_data: 市场数据摘要
        :param indicator_scores: 各指标评分
        :return: (评分 -100 到 100, 报告文本)
        """
        # 缓存检查（5秒内返回缓存结果）
        now = time.time()
        if self._cached_score is not None and (now - self._last_audit_time) < 5:
            return self._cached_score, self._cached_report
        
        # 熔断检查
        if self.fail_count >= AI_MAX_FAIL_COUNT:
            if now - self.last_fail_time < AI_FAIL_COOLDOWN:
                return None, "AI 服务熔断中，请稍后重试"
            else:
                self.fail_count = 0
        
        # 模拟 AI 调用可能失败（5%概率）
        if np.random.random() < 0.05:
            self.fail_count += 1
            self.last_fail_time = now
            return None, "AI 服务暂时不可用"
        
        # 获取市场数据
        if market_data is None:
            from indicators import get_market_summary
            market_data = get_market_summary()
        
        # AI 综合分析
        score, report = self._analyze_market(market_data, indicator_scores)
        
        # 缓存结果
        self._cached_score = score
        self._cached_report = report
        self._last_audit_time = now
        
        return score, report
    
    def _analyze_market(self, market_data: Dict, indicator_scores: Dict = None) -> Tuple[float, str]:
        """
        基于市场数据进行智能分析
        返回与其他指标一致的评分
        """
        score = 0.0
        analysis_points = []
        
        # 1. 趋势分析 (权重: 30%)
        trend = market_data.get('trend', 0)
        if trend > 0:
            trend_score = 30
            analysis_points.append("**趋势分析**: 检测到上升趋势，价格动能偏多")
        elif trend < 0:
            trend_score = -30
            analysis_points.append("**趋势分析**: 检测到下降趋势，价格动能偏空")
        else:
            trend_score = 0
            analysis_points.append("**趋势分析**: 市场处于震荡状态，方向不明")
        score += trend_score
        
        # 2. RSI 分析 (权重: 20%)
        rsi = market_data.get('rsi', 50)
        if rsi > 70:
            rsi_score = -15
            analysis_points.append(f"**RSI 分析**: RSI={rsi:.1f}，超买区域，存在回调风险")
        elif rsi < 30:
            rsi_score = 15
            analysis_points.append(f"**RSI 分析**: RSI={rsi:.1f}，超卖区域，存在反弹机会")
        else:
            rsi_score = (rsi - 50) * 0.3
            analysis_points.append(f"**RSI 分析**: RSI={rsi:.1f}，处于正常区间")
        score += rsi_score
        
        # 3. 成交量分析 (权重: 20%)
        volume_ratio = market_data.get('volume_ratio', 1.0)
        price = market_data.get('price', 3500)
        support = market_data.get('support', 3400)
        resistance = market_data.get('resistance', 3600)
        
        if volume_ratio > 1.5:
            # 放量
            if trend > 0:
                volume_score = 20
                analysis_points.append(f"**成交量**: 放量上涨（{volume_ratio:.1f}倍），多头动能强劲")
            elif trend < 0:
                volume_score = -20
                analysis_points.append(f"**成交量**: 放量下跌（{volume_ratio:.1f}倍），空头动能强劲")
            else:
                volume_score = 5 if price > (support + resistance) / 2 else -5
                analysis_points.append(f"**成交量**: 放量震荡（{volume_ratio:.1f}倍），关注方向突破")
        else:
            volume_score = trend * 5
            analysis_points.append(f"**成交量**: 成交量平稳（{volume_ratio:.1f}倍），市场情绪中性")
        score += volume_score
        
        # 4. 支撑压力位分析 (权重: 15%)
        range_mid = (support + resistance) / 2
        position = (price - support) / (resistance - support) if resistance != support else 0.5
        
        if position > 0.7:
            position_score = -10
            analysis_points.append(f"**位置分析**: 价格接近压力位${resistance:,.0f}，注意突破确认")
        elif position < 0.3:
            position_score = 10
            analysis_points.append(f"**位置分析**: 价格接近支撑位${support:,.0f}，关注支撑有效性")
        else:
            position_score = (position - 0.5) * 10
            analysis_points.append(f"**位置分析**: 价格位于区间中部，支撑压力均有效")
        score += position_score
        
        # 5. 波动率分析 (权重: 15%)
        volatility = market_data.get('volatility', 0.02)
        if volatility > 0.03:
            analysis_points.append(f"**波动率**: 高波动市场（{volatility*100:.1f}%），建议降低仓位")
            score *= 0.85  # 高波动降低信号强度
        else:
            analysis_points.append(f"**波动率**: 波动率正常（{volatility*100:.1f}%），可按计划执行")
        
        # 综合判断
        if indicator_scores:
            # 与其他指标交叉验证
            other_signals = [s for s in indicator_scores.values() if s != 0]
            if other_signals:
                avg_other = sum(other_signals) / len(other_signals)
                if (score > 0 and avg_other > 0) or (score < 0 and avg_other < 0):
                    # AI 与其他指标同向
                    score = score * 1.1
                    analysis_points.append("**信号共振**: AI 分析与其他指标方向一致，信号增强")
                elif abs(score - avg_other) > 30:
                    # AI 与其他指标分歧较大
                    score = score * 0.7
                    analysis_points.append("**信号分歧**: AI 分析与其他指标存在分歧，建议谨慎")
        
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
        
        report = f"""
### AI 审计报告

{chr(10).join(analysis_points)}

**综合评分**: {score:.1f}/100
**建议方向**: {direction}
**信号强度**: {confidence}
"""
        
        return round(score, 2), report
    
    def quick_score(self, market_data: Dict = None) -> float:
        """快速获取 AI 评分（用于决策引擎）"""
        score, _ = self.audit(market_data)
        return score if score is not None else 0


# 全局审计实例
auditor = AIAuditor()
