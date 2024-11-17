from typing import Dict, Optional
import logging
import asyncio
from decimal import Decimal
import time
from datetime import datetime
from pathlib import Path
import sys
from .utils.binance import BinanceClient
from .utils.ronin import RoninClient
from .utils.telegram import TelegramNotifier
import configparser

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class AXSStakingBot:
    def __init__(self, config_path: str = "config/config.ini"):
        """Initialisiert den AXS Staking Bot"""
        self.config = self._load_config(config_path)
        self.binance = BinanceClient(
            api_key=self.config['BINANCE']['api_key'],
            api_secret=self.config['BINANCE']['api_secret']
        )
        self.ronin = RoninClient(
            private_key=self.config['RONIN']['private_key'],
            wallet_address=self.config['RONIN']['wallet_address']
        )
        self.telegram = TelegramNotifier(self.config) if self.config['TELEGRAM'].getboolean('enabled') else None
        self.running = False
        
    def _load_config(self, config_path: str) -> configparser.ConfigParser:
        """Lädt die Konfigurationsdatei"""
        if not Path(config_path).exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
            
        config = configparser.ConfigParser()
        config.read(config_path)
        return config

    async def check_price_conditions(self) -> bool:
        """Überprüft ob die Preisbedingungen für einen Kauf erfüllt sind"""
        try:
            # Hole historische Daten
            klines = await self.binance.get_klines('AXSUSDT', '1h', 24)
            current_price = await self.binance.get_current_price('AXSUSDT')
            
            # Berechne Durchschnittspreis
            prices = [float(k['close_price']) for k in klines]
            avg_price = sum(prices) / len(prices)
            
            # RSI berechnen
            rsi = await self.binance.calculate_rsi('AXSUSDT', 14)
            
            # Kaufbedingungen:
            # 1. Preis mind. 5% unter Durchschnitt
            # 2. RSI unter 30 (überverkauft)
            price_condition = current_price < (avg_price * 0.95)
            rsi_condition = rsi < 30
            
            if price_condition and rsi_condition:
                logger.info(f"Kaufbedingungen erfüllt - Preis: {current_price}, RSI: {rsi}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Fehler bei der Preisanalyse: {e}")
            return False

    async def execute_buy(self, usdt_amount: Decimal) -> Optional[Dict]:
        """Führt den AXS-Kauf auf Binance aus"""
        try:
            order = await self.binance.place_market_buy('AXSUSDT', usdt_amount)
            
            if order and order['status'] == 'FILLED':
                msg = f"Kauf ausgeführt: {order['executedQty']} AXS für {usdt_amount} USDT"
                logger.info(msg)
                if self.telegram:
                    await self.telegram.send_message(msg)
                return order
            
            return None
            
        except Exception as e:
            logger.error(f"Fehler beim Kauf: {e}")
            if self.telegram:
                await self.telegram.send_message(f"Kaufversuch fehlgeschlagen: {e}")
            return None

    async def transfer_to_ronin(self, amount: Decimal) -> Optional[str]:
        """Transferiert AXS zur Ronin Wallet"""
        try:
            withdrawal = await self.binance.withdraw_to_ronin(
                amount=amount,
                address=self.config['RONIN']['wallet_address']
            )
            
            if withdrawal:
                msg = f"Transfer zu Ronin initiiert: {amount} AXS"
                logger.info(msg)
                if self.telegram:
                    await self.telegram.send_message(msg)
                return withdrawal['id']
            
            return None
            
        except Exception as e:
            logger.error(f"Fehler beim Transfer: {e}")
            if self.telegram:
                await self.telegram.send_message(f"Transfer fehlgeschlagen: {e}")
            return None

    async def stake_axs(self, amount: Decimal) -> Optional[str]:
        """Führt das Staking in der Ronin Wallet durch"""
        try:
            tx_hash = await self.ronin.stake_axs(amount)
            
            if tx_hash:
                msg = f"Staking erfolgreich: {amount} AXS"
                logger.info(msg)
                if self.telegram:
                    await self.telegram.send_message(msg)
                return tx_hash
            
            return None
            
        except Exception as e:
            logger.error(f"Fehler beim Staking: {e}")
            if self.telegram:
                await self.telegram.send_message(f"Staking fehlgeschlagen: {e}")
            return None

    async def run(self):
        """Hauptloop des Bots"""
        self.running = True
        logger.info("Bot gestartet")
        if self.telegram:
            await self.telegram.send_message("Bot gestartet")
        
        while self.running:
            try:
                # Prüfe Binance USDT Balance
                usdt_balance = await self.binance.get_balance('USDT')
                usdt_amount = Decimal(self.config['BOT_SETTINGS']['usdt_amount'])
                
                if usdt_balance >= usdt_amount:
                    if await self.check_price_conditions():
                        # Kaufe AXS
                        if order := await self.execute_buy(usdt_amount):
                            await asyncio.sleep(10)  # Warte bis Order abgewickelt
                            
                            # Transfer zu Ronin
                            if tx_hash := await self.transfer_to_ronin(Decimal(order['executedQty'])):
                                await asyncio.sleep(900)  # Warte ~15min auf Transfer
                                
                                # Stake AXS
                                await self.stake_axs(Decimal(order['executedQty']))
                
                # Warte das konfigurierte Intervall
                await asyncio.sleep(int(self.config['BOT_SETTINGS']['check_interval']))
                
            except Exception as e:
                logger.error(f"Fehler im Hauptloop: {e}")
                if self.telegram:
                    await self.telegram.send_message(f"Fehler aufgetreten: {e}")
                await asyncio.sleep(60)

    async def stop(self):
        """Stoppt den Bot"""
        self.running = False
        logger.info("Bot gestoppt")
        if self.telegram:
            await self.telegram.send_message("Bot gestoppt")

if __name__ == "__main__":
    bot = AXSStakingBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        asyncio.run(bot.stop())