from typing import Dict, List, Optional
from decimal import Decimal
import logging
import numpy as np
from binance.client import Client
from binance.exceptions import BinanceAPIException

logger = logging.getLogger(__name__)

class BinanceClient:
    def __init__(self, api_key: str, api_secret: str):
        """Initialisiert den Binance Client"""
        self.client = Client(api_key, api_secret)

    async def get_balance(self, asset: str) -> Decimal:
        """Holt den Kontostand für ein Asset"""
        try:
            balance = self.client.get_asset_balance(asset=asset)
            return Decimal(balance['free'])
        except BinanceAPIException as e:
            logger.error(f"Fehler beim Abrufen des {asset} Kontostands: {e}")
            return Decimal('0')

    async def get_klines(self, symbol: str, interval: str, limit: int) -> List[Dict]:
        """Holt Kline/Candlestick-Daten"""
        try:
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            # Formatiere Kline-Daten
            formatted_klines = []
            for k in klines:
                formatted_klines.append({
                    'open_time': k[0],
                    'open_price': float(k[1]),
                    'high_price': float(k[2]),
                    'low_price': float(k[3]),
                    'close_price': float(k[4]),
                    'volume': float(k[5]),
                    'close_time': k[6]
                })
                
            return formatted_klines
            
        except BinanceAPIException as e:
            logger.error(f"Fehler beim Abrufen der Kline-Daten: {e}")
            return []

    async def get_current_price(self, symbol: str) -> float:
        """Holt den aktuellen Preis eines Symbols"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            logger.error(f"Fehler beim Abrufen des aktuellen Preises: {e}")
            return 0.0

    async def calculate_rsi(self, symbol: str, period: int = 14) -> float:
        """Berechnet den RSI (Relative Strength Index)"""
        try:
            klines = await self.get_klines(symbol, '1h', period + 1)
            if not klines:
                return 0.0
                
            # Preisänderungen berechnen
            changes = []
            for i in range(1, len(klines)):
                change = klines[i]['close_price'] - klines[i-1]['close_price']
                changes.append(change)
                
            # Positive und negative Änderungen trennen
            gains = [change if change > 0 else 0 for change in changes]
            losses = [-change if change < 0 else 0 for change in changes]
            
            # Durchschnitte berechnen
            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)
            
            if avg_loss == 0:
                return 100.0
                
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
            
        except Exception as e:
            logger.error(f"Fehler bei der RSI-Berechnung: {e}")
            return 0.0

    async def place_market_buy(self, symbol: str, usdt_amount: Decimal) -> Optional[Dict]:
        """Platziert eine Market Buy Order"""
        try:
            # Hole aktuellen Preis für Mengenberechnung
            price = await self.get_current_price(symbol)
            if not price:
                return None
                
            # Berechne Kaufmenge
            quantity = float(usdt_amount) / price
            
            # Runde auf die richtige Dezimalstelle
            info = self.client.get_symbol_info(symbol)
            lot_size = next(f for f in info['filters'] if f['filterType'] == 'LOT_SIZE')
            step_size = Decimal(lot_size['stepSize'])
            quantity = float(Decimal(str(quantity)).quantize(step_size))
            
            # Platziere Order
            order = self.client.order_market_buy(
                symbol=symbol,
                quantity=quantity
            )
            
            return order
            
        except BinanceAPIException as e:
            logger.error(f"Fehler beim Platzieren der Kauforder: {e}")
            return None

    async def withdraw_to_ronin(self, amount: Decimal, address: str) -> Optional[Dict]:
        """Führt einen Withdrawal zu Ronin durch"""
        try:
            withdrawal = self.client.withdraw(
                asset='AXS',
                address=address,
                amount=float(amount),
                network='Ronin'
            )
            return withdrawal
        except BinanceAPIException as e:
            logger.error(f"Fehler beim Withdrawal: {e}")
            return None