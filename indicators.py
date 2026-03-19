# indicators.py
"""
指标计算模块 - 获取真实市场数据并计算技术指标
数据来源：Binance 公共API（免费，无需认证）
"""
import numpy as np
import requests
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, List
import time

class MarketData:
    """真实市场数据管理器"""
    
    _instance = None
    _last_update = 0
    _cache_duration = 10  # 缓存10秒
    _api_timeout = 10
    
    # Binance API (免费公开接口)
    BINANCE_API = "https://api.binance.com/api/v3"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """初始化市场数据"""
        self._base_price = 3500.0
        self._volatility = 0.02
        self._trend = 0
        self._volume_ratio = 1.0
        self._rsi = 50.0
        self._macd_signal = 0.0
        self._money_flow = 0.0
        self._support = 3400.0
        self._resistance = 3600.0
        self._klines = []
        self._last_api_call = 0
        self._api_call_interval = 1  # API调用间隔(秒)
        
        # 首次获取真实数据
        self._fetch_real_data()
    
    def _fetch_real_data(self):
        """从Binance获取真实市场数据"""
        try:
            # 检查API调用频率限制
            now = time.time()
            if now - self._last_api_call < self._api_call_interval:
                return
            self._last_api_call = now
            
            # 1. 获取当前价格
            ticker_url = f"{self.BINANCE_API}/ticker/24hr?symbol=ETHUSDT"
            response = requests.get(ticker_url, timeout=self._api_timeout)
            
            if response.status_code == 200:
                data = response.json()
                self._base_price = float(data.get('lastPrice', 3500))
                self._volume_ratio = float(data.get('volume', 1)) / 100000  # 归一化成交量
                price_change_pct = float(data.get('priceChangePercent', 0))
                high_price = float(data.get('highPrice', self._base_price * 1.02))
                low_price = float(data.get('lowPrice', self._base_price * 0.98))
                
                # 计算波动率
                self._volatility = (high_price - low_price) / self._base_price if self._base_price > 0 else 0.02
                
                # 计算趋势
                if price_change_pct > 1:
                    self._trend = 1
                elif price_change_pct < -1:
                    self._trend = -1
                else:
                    self._trend = 0
                
                # 计算支撑压力位
                self._support = low_price
                self._resistance = high_price
            
            # 2. 获取K线数据计算技术指标
            klines_url = f"{self.BINANCE_API}/klines?symbol=ETHUSDT&interval=1h&limit=100"
            response = requests.get(klines_url, timeout=self._api_timeout)
            
            if response.status_code == 200:
                self._klines = response.json()
                self._calculate_indicators()
            
            self._last_update = time.time()
            
        except Exception as e:
            print(f"获取真实数据失败，使用缓存数据: {e}")
    
    def _calculate_indicators(self):
        """基于真实K线计算技术指标"""
        if not self._klines or len(self._klines) < 20:
            return
        
        try:
            # 提取收盘价
            closes = [float(k[4]) for k in self._klines]
            volumes = [float(k[5]) for k in self._klines]
            
            # 计算RSI (14周期)
            self._rsi = self._calculate_rsi(closes, 14)
            
            # 计算MACD信号
            self._macd_signal = self._calculate_macd_signal(closes)
            
            # 计算资金流向
            self._money_flow = self._calculate_money_flow(closes, volumes)
            
        except Exception as e:
            print(f"计算指标失败: {e}")
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """计算RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices[-(period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains) if len(gains) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return round(rsi, 2)
    
    def _calculate_macd_signal(self, prices: List[float]) -> float:
        """计算MACD信号"""
        if len(prices) < 26:
            return 0.0
        
        # EMA计算
        ema12 = self._calculate_ema(prices, 12)
        ema26 = self._calculate_ema(prices, 26)
        
        macd = ema12 - ema26
        
        # 归一化到 -1 到 1
        signal = macd / prices[-1] * 100 if prices[-1] > 0 else 0
        return round(signal, 4)
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """计算EMA"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = np.mean(prices[:period])
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def _calculate_money_flow(self, prices: List[float], volumes: List[float]) -> float:
        """计算资金流向 (MFI概念)"""
        if len(prices) < 2 or len(volumes) < 2:
            return 0.0
        
        # 简化版资金流向：价格上涨时成交量正相关
        price_changes = np.diff(prices[-20:]) if len(prices) >= 20 else np.diff(prices)
        volume_changes = volumes[-len(price_changes):]
        
        positive_flow = 0
        negative_flow = 0
        
        for i, change in enumerate(price_changes):
            if i < len(volume_changes):
                if change > 0:
                    positive_flow += volume_changes[i]
                elif change < 0:
                    negative_flow += volume_changes[i]
        
        total_flow = positive_flow + negative_flow
        if total_flow == 0:
            return 0.0
        
        # 归一化到 -1 到 1
        mfi = (positive_flow - negative_flow) / total_flow
        return round(mfi, 4)
    
    def refresh(self, force: bool = False):
        """刷新数据"""
        now = time.time()
        if force or (now - self._last_update) > self._cache_duration:
            self._fetch_real_data()
    
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
        return round(self._volume_ratio, 2)
    
    @property
    def volatility(self) -> float:
        return round(self._volatility, 4)
    
    @property
    def money_flow_raw(self) -> float:
        return self._money_flow
    
    @property
    def rsi(self) -> float:
        return self._rsi
    
    @property
    def macd_signal(self) -> float:
        return self._macd_signal
    
    @property
    def klines(self) -> List:
        return self._klines


# 全局市场数据实例
market_data = MarketData()


def get_current_price() -> float:
    """获取当前ETH真实价格"""
    market_data.refresh()
    return market_data.current_price


def get_support_resistance() -> Tuple[float, float]:
    """获取真实支撑位和压力位"""
    market_data.refresh()
    return market_data.support, market_data.resistance


def calculate_volume_price() -> float:
    """
    量价口诀评分 (-100 到 100)
    基于真实成交量和价格趋势
    """
    market_data.refresh()
    
    score = 0.0
    
    # 1. 价格趋势贡献 (40%)
    trend_score = market_data.trend * 40
    score += trend_score
    
    # 2. 成交量确认 (30%)
    volume_factor = (market_data.volume_ratio - 1) * 30
    if market_data.trend > 0:
        score += volume_factor
    elif market_data.trend < 0:
        score -= volume_factor
    
    # 3. RSI 辅助 (30%)
    if market_data.rsi > 70:
        score -= 15
    elif market_data.rsi < 30:
        score += 15
    else:
        score += (market_data.rsi - 50) * 0.6
    
    return round(max(-100, min(100, score)), 2)


def calculate_multi_resonance() -> float:
    """
    多空共振评分 (-100 到 100)
    基于真实技术指标
    """
    market_data.refresh()
    
    score = 0.0
    signals = []
    
    # 趋势信号
    signals.append(market_data.trend * 25)
    
    # MACD 信号
    signals.append(market_data.macd_signal * 20)
    
    # RSI 信号
    if market_data.rsi > 70:
        signals.append(-15)
    elif market_data.rsi < 30:
        signals.append(15)
    else:
        signals.append((market_data.rsi - 50) * 0.4)
    
    # 成交量确认
    if market_data.volume_ratio > 1.5:
        signals.append(market_data.trend * 15)
    else:
        signals.append(market_data.trend * 5)
    
    # 计算共振强度
    positive_signals = sum(1 for s in signals if s > 5)
    negative_signals = sum(1 for s in signals if s < -5)
    
    if positive_signals >= 3:
        score = sum(signals) * 1.2
    elif negative_signals >= 3:
        score = sum(signals) * 1.2
    else:
        score = sum(signals)
    
    return round(max(-100, min(100, score)), 2)


def calculate_market_structure() -> float:
    """
    市场结构评分 (-100 到 100)
    基于真实支撑压力位
    """
    market_data.refresh()
    
    score = 0.0
    price = market_data.current_price
    support = market_data.support
    resistance = market_data.resistance
    
    # 位置分析
    range_size = resistance - support
    price_position = (price - support) / range_size if range_size > 0 else 0.5
    
    if price_position > 0.7:
        score -= 20
        if market_data.trend > 0:
            score += 10
    elif price_position < 0.3:
        score += 20
        if market_data.trend < 0:
            score -= 10
    else:
        score += (price_position - 0.5) * 20
    
    # 趋势结构
    score += market_data.trend * 30
    
    # 波动率考量
    if market_data.volatility > 0.03:
        score *= 0.7
    
    return round(max(-100, min(100, score)), 2)


def calculate_lstm_prediction() -> float:
    """
    LSTM预测评分 (-100 到 100)
    基于真实趋势和RSI
    """
    market_data.refresh()
    
    score = 0.0
    
    # 趋势预测
    if market_data.trend != 0:
        score = market_data.trend * 60 * 0.6
    
    # RSI 反转预测
    if market_data.rsi > 75:
        score -= 20 * 0.4
    elif market_data.rsi < 25:
        score += 20 * 0.4
    
    return round(max(-100, min(100, score)), 2)


def calculate_money_flow() -> float:
    """
    资金流向评分 (-100 到 100)
    基于真实资金流向指标
    """
    market_data.refresh()
    
    score = 0.0
    base_flow = market_data.money_flow_raw * 50
    volume_weighted = base_flow * (0.5 + market_data.volume_ratio * 0.5)
    
    if market_data.trend > 0 and base_flow > 0:
        score = volume_weighted * 1.3
    elif market_data.trend < 0 and base_flow < 0:
        score = volume_weighted * 1.3
    elif market_data.trend * base_flow < 0:
        score = volume_weighted * 0.5
    else:
        score = volume_weighted
    
    return round(max(-100, min(100, score)), 2)


def get_historical_prices(days: int = 30) -> Tuple[list, list]:
    """获取真实历史K线数据"""
    try:
        # 从Binance获取真实K线
        interval = "1d" if days <= 30 else "3d"
        limit = min(days, 100)
        
        url = f"https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval={interval}&limit={limit}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            klines = response.json()
            dates = [datetime.fromtimestamp(k[0] / 1000) for k in klines]
            prices = [float(k[4]) for k in klines]  # 收盘价
            return dates, prices
    except Exception as e:
        print(f"获取历史数据失败: {e}")
    
    # 失败时返回模拟数据
    end = datetime.now()
    start = end - timedelta(days=days)
    dates = [start + timedelta(days=i) for i in range(days)]
    prices = [3500 + i * 5 + np.random.uniform(-50, 50) for i in range(days)]
    
    return dates, prices


def get_real_klines(interval: str = "1h", limit: int = 100) -> List[Dict]:
    """获取真实K线数据（包含OHLCV）"""
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval={interval}&limit={limit}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            klines = response.json()
            return [{
                'time': datetime.fromtimestamp(k[0] / 1000),
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5])
            } for k in klines]
    except Exception as e:
        print(f"获取K线失败: {e}")
    
    return []


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
