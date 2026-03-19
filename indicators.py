# indicators.py
"""
指标计算模块 - 基于统一市场数据计算各项技术指标
确保指标之间逻辑一致，避免随机数据导致的矛盾
"""
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import hashlib

class MarketData:
    """统一市场数据管理器，确保所有指标使用相同的数据源"""
    
    _instance = None
    _last_update = 0
    _cache_duration = 5  # 缓存5秒
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """初始化市场数据"""
        np.random.seed(int(datetime.now().timestamp()) % 10000)
        self._base_price = 3500.0
        self._volatility = 0.02
        self._trend = 0  # -1: 下跌, 0: 震荡, 1: 上涨
        self._generate_new_data()
    
    def _generate_new_data(self):
        """生成新的市场数据快照"""
        # 趋势变化（10%概率改变趋势）
        if np.random.random() < 0.1:
            self._trend = np.random.choice([-1, 0, 1])
        
        # 价格变动
        trend_factor = self._trend * np.random.uniform(0.001, 0.005)
        noise = np.random.normal(0, self._volatility * 0.5)
        price_change = (trend_factor + noise) * self._base_price
        self._base_price = max(3000, min(4000, self._base_price + price_change))
        
        # 生成相关市场参数
        self._volume_ratio = np.random.uniform(0.5, 2.0)  # 成交量比
        self._volatility_current = np.random.uniform(0.01, 0.05)
        self._money_flow = np.random.uniform(-1, 1)  # 资金流向
        
        # 计算技术指标基础值
        self._rsi = 50 + self._trend * np.random.uniform(10, 25) + np.random.uniform(-10, 10)
        self._rsi = max(10, min(90, self._rsi))
        
        self._macd_signal = self._trend * np.random.uniform(0.5, 1.5)
        
        # 支撑位和压力位
        self._support = self._base_price * (1 - np.random.uniform(0.02, 0.05))
        self._resistance = self._base_price * (1 + np.random.uniform(0.02, 0.05))
        
        self._last_update = datetime.now().timestamp()
    
    def refresh(self, force: bool = False):
        """刷新数据（带缓存）"""
        now = datetime.now().timestamp()
        if force or (now - self._last_update) > self._cache_duration:
            self._generate_new_data()
    
    @property
    def current_price(self) -> float:
        return round(self._base_price, 2)
    
    @property
    def trend(self) -> int:
        return self._trend
    
    @property
    def support(self) -> float:
        return round(self._support, 2)
    
    @property
    def resistance(self) -> float:
        return round(self._resistance, 2)
    
    @property
    def volume_ratio(self) -> float:
        return self._volume_ratio
    
    @property
    def volatility(self) -> float:
        return self._volatility_current
    
    @property
    def money_flow_raw(self) -> float:
        return self._money_flow
    
    @property
    def rsi(self) -> float:
        return self._rsi
    
    @property
    def macd_signal(self) -> float:
        return self._macd_signal

# 全局市场数据实例
market_data = MarketData()


def get_current_price() -> float:
    """获取当前ETH价格"""
    market_data.refresh()
    return market_data.current_price


def get_support_resistance() -> Tuple[float, float]:
    """获取支撑位和压力位"""
    market_data.refresh()
    return market_data.support, market_data.resistance


def calculate_volume_price() -> float:
    """
    量价口诀评分 (-100 到 100)
    基于成交量、价格趋势综合判断
    正数表示做多信号，负数表示做空信号
    """
    market_data.refresh()
    
    score = 0.0
    
    # 1. 价格趋势贡献 (40%)
    trend_score = market_data.trend * 40
    score += trend_score
    
    # 2. 成交量确认 (30%)
    # 放量上涨 = 强多, 放量下跌 = 强空
    volume_factor = (market_data.volume_ratio - 1) * 30
    if market_data.trend > 0:
        score += volume_factor  # 放量上涨增强多头
    elif market_data.trend < 0:
        score -= volume_factor  # 放量下跌增强空头
    
    # 3. RSI 辅助 (30%)
    if market_data.rsi > 70:
        score -= 15  # 超买，减弱多头信号
    elif market_data.rsi < 30:
        score += 15  # 超卖，减弱空头信号
    else:
        score += (market_data.rsi - 50) * 0.6
    
    return round(max(-100, min(100, score)), 2)


def calculate_multi_resonance() -> float:
    """
    多空共振评分 (-100 到 100)
    检测多个技术指标是否同向共振
    """
    market_data.refresh()
    
    score = 0.0
    signals = []
    
    # 趋势信号
    signals.append(market_data.trend * 25)
    
    # MACD 信号
    signals.append(market_data.macd_signal * 20)
    
    # RSI 信号 (反转逻辑)
    if market_data.rsi > 70:
        signals.append(-15)  # 超买，空头信号
    elif market_data.rsi < 30:
        signals.append(15)   # 超卖，多头信号
    else:
        signals.append((market_data.rsi - 50) * 0.4)
    
    # 成交量确认
    if market_data.volume_ratio > 1.5:
        # 高成交量确认趋势
        signals.append(market_data.trend * 15)
    else:
        # 低成交量，信号减弱
        signals.append(market_data.trend * 5)
    
    # 计算共振强度 - 同向信号加权
    positive_signals = sum(1 for s in signals if s > 5)
    negative_signals = sum(1 for s in signals if s < -5)
    
    if positive_signals >= 3:
        score = sum(signals) * 1.2  # 多头共振增强
    elif negative_signals >= 3:
        score = sum(signals) * 1.2  # 空头共振增强
    else:
        score = sum(signals)
    
    return round(max(-100, min(100, score)), 2)


def calculate_market_structure() -> float:
    """
    市场结构评分 (-100 到 100)
    分析高低点结构、趋势线
    """
    market_data.refresh()
    
    score = 0.0
    price = market_data.current_price
    support = market_data.support
    resistance = market_data.resistance
    
    # 1. 价格相对于支撑压力的位置 (40%)
    range_size = resistance - support
    price_position = (price - support) / range_size if range_size > 0 else 0.5
    
    if price_position > 0.7:
        # 接近压力位
        score -= 20
        if market_data.trend > 0:
            score += 10  # 突破尝试
    elif price_position < 0.3:
        # 接近支撑位
        score += 20
        if market_data.trend < 0:
            score -= 10  # 破位尝试
    else:
        score += (price_position - 0.5) * 20
    
    # 2. 趋势结构 (40%)
    score += market_data.trend * 30
    
    # 3. 波动率考量 (20%)
    if market_data.volatility > 0.03:
        # 高波动，结构可能被破坏
        score *= 0.7
    
    return round(max(-100, min(100, score)), 2)


def calculate_lstm_prediction() -> float:
    """
    LSTM预测评分 (-100 到 100)
    模拟机器学习模型的趋势预测
    """
    market_data.refresh()
    
    score = 0.0
    
    # 基于当前市场状态的综合预测
    # LSTM 通常会学习到趋势惯性
    trend_weight = 0.6
    
    # 趋势预测
    if market_data.trend != 0:
        score = market_data.trend * 60 * trend_weight
    
    # RSI 反转预测
    if market_data.rsi > 75:
        score -= 20 * (1 - trend_weight)  # 预测反转
    elif market_data.rsi < 25:
        score += 20 * (1 - trend_weight)
    
    # 添加一些预测不确定性
    noise = np.random.normal(0, 10)
    score += noise
    
    return round(max(-100, min(100, score)), 2)


def calculate_money_flow() -> float:
    """
    资金流向评分 (-100 到 100)
    分析主力资金进出
    """
    market_data.refresh()
    
    score = 0.0
    
    # 基础资金流向
    base_flow = market_data.money_flow_raw * 50
    
    # 成交量加权
    volume_weighted = base_flow * (0.5 + market_data.volume_ratio * 0.5)
    
    # 趋势确认
    if market_data.trend > 0 and base_flow > 0:
        score = volume_weighted * 1.3  # 资金流入 + 上涨趋势 = 强多
    elif market_data.trend < 0 and base_flow < 0:
        score = volume_weighted * 1.3  # 资金流出 + 下跌趋势 = 强空
    elif market_data.trend * base_flow < 0:
        score = volume_weighted * 0.5  # 背离，信号减弱
    else:
        score = volume_weighted
    
    return round(max(-100, min(100, score)), 2)


def get_historical_prices(days: int = 30) -> Tuple[list, list]:
    """生成连续的历史价格数据用于图表"""
    end = datetime.now()
    start = end - timedelta(days=days)
    dates = [start + timedelta(days=i) for i in range(days)]
    
    # 生成连续的价格数据
    base = 3400
    prices = []
    current_price = base
    
    for i in range(days):
        # 模拟价格走势
        trend = np.sin(i / 10) * 50  # 周期性波动
        noise = np.random.normal(0, 30)
        current_price = base + trend + noise + i * 2
        prices.append(round(current_price, 2))
    
    return dates, prices


def get_market_summary() -> Dict:
    """获取市场数据摘要"""
    market_data.refresh()
    return {
        'price': market_data.current_price,
        'support': market_data.support,
        'resistance': market_data.resistance,
        'trend': market_data.trend,
        'rsi': market_data.rsi,
        'volume_ratio': market_data.volume_ratio,
        'volatility': market_data.volatility
    }
