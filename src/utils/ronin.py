from typing import Optional
from decimal import Decimal
import logging
from web3 import Web3
from eth_account import Account
from eth_account.signers.local import LocalAccount

logger = logging.getLogger(__name__)

# AXS Contract Addresses
AXS_CONTRACT = "0x97a9107C1793BC407d6F527b77e7fff4D812bece"
STAKING_CONTRACT = "0x05b0bb3c1c320b280501b86706c3551995bc8571"

class RoninClient:
    def __init__(self, private_key: str, wallet_address: str):
        """Initialisiert den Ronin Client"""
        self.web3 = Web3(Web3.HTTPProvider('https://api.roninchain.com/rpc'))
        self.account: LocalAccount = Account.from_key(private_key)
        self.wallet_address = wallet_address
        
        # Contract ABIs laden
        self.axs_contract = self.web3.eth.contract(
            address=AXS_CONTRACT,
            abi=self._load_abi('axs_token_abi.json')
        )
        self.staking_contract = self.web3.eth.contract(
            address=STAKING_CONTRACT,
            abi=self._load_abi('staking_contract_abi.json')
        )

    def _load_abi(self, filename: str) -> str:
        """Lädt eine ABI aus einer JSON-Datei"""
        try:
            with open(f"config/abi/{filename}", 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Fehler beim Laden der ABI {filename}: {e}")
            raise

    async def get_axs_balance(self) -> Decimal:
        """Holt den AXS-Kontostand der Wallet"""
        try:
            balance = self.axs_contract.functions.balance