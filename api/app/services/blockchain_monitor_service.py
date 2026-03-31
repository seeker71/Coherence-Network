"""Blockchain Monitor Service — abstract interface for BTC/ETH tx monitoring.

Implements spec 122 R2: monitors blockchain for incoming deposits,
tracks confirmations, and signals when confirmation threshold is reached.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TxStatus:
    tx_hash: str
    confirmations: int
    confirmations_required: int
    amount_crypto: float
    detected_at: datetime
    confirmed_at: Optional[datetime] = None
    is_confirmed: bool = False


class BlockchainMonitor(ABC):
    @abstractmethod
    def get_tx_status(self, tx_hash: str) -> Optional[TxStatus]:
        raise NotImplementedError

    @abstractmethod
    def is_valid_address(self, address: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_current_block_height(self) -> int:
        raise NotImplementedError


class BTCMonitor(BlockchainMonitor):
    def __init__(self, confirmations_required: int = 6):
        self.confirmations_required = confirmations_required

    def get_tx_status(self, tx_hash: str) -> Optional[TxStatus]:
        return None

    def is_valid_address(self, address: str) -> bool:
        if not address:
            return False
        if address.startswith("bc1"):
            return len(address) >= 26 and len(address) <= 90
        if address.startswith("1") or address.startswith("3"):
            return len(address) >= 26 and len(address) <= 35
        return False

    def get_current_block_height(self) -> int:
        return 0


class ETHMonitor(BlockchainMonitor):
    def __init__(self, confirmations_required: int = 12):
        self.confirmations_required = confirmations_required

    def get_tx_status(self, tx_hash: str) -> Optional[TxStatus]:
        return None

    def is_valid_address(self, address: str) -> bool:
        if not address:
            return False
        return address.startswith("0x") and len(address) == 42

    def get_current_block_height(self) -> int:
        return 0


_btc_monitor: Optional[BlockchainMonitor] = None
_eth_monitor: Optional[BlockchainMonitor] = None


def get_btc_monitor() -> BlockchainMonitor:
    global _btc_monitor
    if _btc_monitor is None:
        _btc_monitor = BTCMonitor()
    return _btc_monitor


def get_eth_monitor() -> BlockchainMonitor:
    global _eth_monitor
    if _eth_monitor is None:
        _eth_monitor = ETHMonitor()
    return _eth_monitor


def set_monitors(btc: BlockchainMonitor, eth: BlockchainMonitor) -> None:
    global _btc_monitor, _eth_monitor
    _btc_monitor = btc
    _eth_monitor = eth
