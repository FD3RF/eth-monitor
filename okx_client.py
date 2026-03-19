# okx_client.py
"""
OKX API 客户端 - 支持真实和模拟模式
"""
import hmac
import base64
import hashlib
import datetime
import json
from typing import Dict, Optional
import requests
import streamlit as st


class OKXClient:
    def __init__(self, api_key: str = "", api_secret: str = "", passphrase: str = "", simulate: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.base_url = "https://www.okx.com"
        self.simulate = simulate  # 模拟盘模式
        self._connected = False
    
    def _get_timestamp(self) -> str:
        """获取 ISO 格式时间戳"""
        return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def _sign(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        """生成签名"""
        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(self.api_secret, encoding='utf-8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()
    
    def _get_headers(self, method: str, request_path: str, body: str = '') -> Dict:
        """获取请求头"""
        timestamp = self._get_timestamp()
        sign = self._sign(timestamp, method, request_path, body)
        
        headers = {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': sign,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
        
        if self.simulate:
            headers['x-simulated-trading'] = '1'
        
        return headers
    
    def _request(self, method: str, endpoint: str, params: Dict = None, body: Dict = None) -> Dict:
        """发送请求"""
        if not self.api_key or not self.api_secret or not self.passphrase:
            return self._mock_response(endpoint, params)
        
        url = self.base_url + endpoint
        body_str = json.dumps(body) if body else ''
        
        headers = self._get_headers(method, endpoint, body_str)
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=body, timeout=10)
            else:
                return {'code': '-1', 'msg': '不支持的请求方法'}
            
            return response.json()
        except Exception as e:
            return {'code': '-1', 'msg': str(e)}
    
    def _mock_response(self, endpoint: str, params: Dict = None) -> Dict:
        """模拟响应"""
        if 'account' in endpoint:
            return {
                'code': '0',
                'msg': '',
                'data': [{
                    'totalEq': '10000.00',
                    'isoEq': '10000.00',
                    'adjEq': '10000.00',
                    'details': [{
                        'ccy': 'USDT',
                        'cashBal': '8500.00',
                        'uTime': datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
                    }]
                }]
            }
        elif 'ticker' in endpoint:
            return {
                'code': '0',
                'data': [{
                    'instId': params.get('instId', 'ETH-USDT-SWAP'),
                    'last': '3500.00',
                    'high24h': '3600.00',
                    'low24h': '3400.00',
                    'vol24h': '100000'
                }]
            }
        elif 'order' in endpoint:
            return {'code': '0', 'msg': '模拟下单成功', 'data': [{'ordId': '123456'}]}
        
        return {'code': '0', 'msg': '模拟响应'}
    
    def get_account(self) -> Dict:
        """获取账户信息"""
        return self._request('GET', '/api/v5/account/balance')
    
    def get_ticker(self, instId: str = 'ETH-USDT-SWAP') -> Dict:
        """获取行情"""
        return self._request('GET', '/api/v5/market/ticker', {'instId': instId})
    
    def get_positions(self, instId: str = None) -> Dict:
        """获取持仓"""
        params = {'instId': instId} if instId else {}
        return self._request('GET', '/api/v5/account/positions', params)
    
    def place_order(
        self,
        instId: str,
        tdMode: str,
        side: str,
        posSide: str,
        sz: float,
        px: float = None,
        ordType: str = 'limit'
    ) -> Dict:
        """
        下单
        :param instId: 产品ID，如 'ETH-USDT-SWAP'
        :param tdMode: 交易模式，'cross' 全仓, 'isolated' 逐仓
        :param side: 方向，'buy' 或 'sell'
        :param posSide: 持仓方向，'long' 或 'short'
        :param sz: 数量
        :param px: 价格（限价单必填）
        :param ordType: 订单类型，'limit' 或 'market'
        """
        body = {
            'instId': instId,
            'tdMode': tdMode,
            'side': side,
            'posSide': posSide,
            'sz': str(sz),
            'ordType': ordType
        }
        
        if ordType == 'limit' and px:
            body['px'] = str(px)
        
        result = self._request('POST', '/api/v5/trade/order', body=body)
        
        if result.get('code') == '0':
            st.success(f"下单成功: {side} {sz} 张 {instId} {'@ ' + str(px) if px else '市价'}")
            self._connected = True
        else:
            st.error(f"下单失败: {result.get('msg', '未知错误')}")
        
        return result
    
    def close_position(self, instId: str, posSide: str) -> Dict:
        """平仓"""
        body = {
            'instId': instId,
            'posSide': posSide,
            'mgnMode': 'cross'
        }
        return self._request('POST', '/api/v5/trade/close-position', body=body)
    
    def test_connection(self) -> bool:
        """测试连接"""
        result = self.get_account()
        self._connected = result.get('code') == '0'
        return self._connected


class MockOKXClient(OKXClient):
    """纯模拟客户端，用于测试"""
    
    def __init__(self):
        super().__init__("", "", "")
        self.balance = 10000.0
        self.positions = []
    
    def get_account(self) -> Dict:
        return {
            'code': '0',
            'msg': '',
            'data': [{
                'totalEq': str(self.balance),
                'details': [{
                    'ccy': 'USDT',
                    'cashBal': str(self.balance * 0.85)
                }]
            }]
        }
    
    def place_order(self, instId, tdMode, side, posSide, sz, px=None, ordType='limit'):
        # 模拟更新余额
        if side == 'buy':
            self.positions.append({
                'instId': instId,
                'posSide': posSide,
                'sz': sz,
                'avgPx': px or 3500
            })
            st.success(f"[模拟] 下单成功: {side} {sz} 张 {instId} @ {px}")
        else:
            st.success(f"[模拟] 平仓成功: {side} {sz} 张 {instId} @ {px}")
        
        return {'code': '0', 'msg': '模拟成功', 'data': [{'ordId': 'mock-' + str(hash(str(sz)))[-6:]}]}
