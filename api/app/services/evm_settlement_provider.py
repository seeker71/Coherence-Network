from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Any

import httpx


_HEX_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


@dataclass(frozen=True)
class EvmSettlementConfig:
    rpc_url: str
    chain_id: int
    private_key: str
    gas_limit: int = 21_000
    amount_decimals: int = 18
    confirm_timeout_seconds: float = 90.0
    confirm_poll_seconds: float = 3.0
    min_confirmations: int = 1

    @classmethod
    def from_env(cls) -> EvmSettlementConfig:
        required = {
            "EVM_SETTLEMENT_RPC_URL": (os.getenv("EVM_SETTLEMENT_RPC_URL") or "").strip(),
            "EVM_SETTLEMENT_CHAIN_ID": (os.getenv("EVM_SETTLEMENT_CHAIN_ID") or "").strip(),
            "EVM_SETTLEMENT_PRIVATE_KEY": (os.getenv("EVM_SETTLEMENT_PRIVATE_KEY") or "").strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            joined = ",".join(sorted(missing))
            raise ValueError(f"missing_required_env:{joined}")

        return cls(
            rpc_url=required["EVM_SETTLEMENT_RPC_URL"],
            chain_id=int(required["EVM_SETTLEMENT_CHAIN_ID"]),
            private_key=required["EVM_SETTLEMENT_PRIVATE_KEY"],
            gas_limit=int((os.getenv("EVM_SETTLEMENT_GAS_LIMIT") or "21000").strip()),
            amount_decimals=int((os.getenv("EVM_SETTLEMENT_AMOUNT_DECIMALS") or "18").strip()),
            confirm_timeout_seconds=float((os.getenv("EVM_SETTLEMENT_CONFIRM_TIMEOUT_SECONDS") or "90").strip()),
            confirm_poll_seconds=float((os.getenv("EVM_SETTLEMENT_CONFIRM_POLL_SECONDS") or "3").strip()),
            min_confirmations=max(1, int((os.getenv("EVM_SETTLEMENT_MIN_CONFIRMATIONS") or "1").strip())),
        )


class EvmNativeSettlementProvider:
    """Broadcast native EVM payouts and confirm receipts over JSON-RPC."""

    def __init__(self, config: EvmSettlementConfig):
        self._config = config
        self._account = self._load_account()
        self._sender_address = str(self._account.from_key(config.private_key).address)
        self._next_nonce_value: int | None = None

    async def send_payout(
        self,
        *,
        distribution_id: str,
        contributor_id: str,
        wallet_address: str,
        amount: Decimal,
    ) -> str:
        if not _HEX_ADDRESS_RE.fullmatch(wallet_address):
            raise ValueError("invalid_wallet_address")
        value_wei = self._decimal_to_wei(amount)
        if value_wei <= 0:
            raise ValueError("payout_amount_must_be_positive")

        nonce = await self._next_nonce()
        gas_price = await self._rpc_int("eth_gasPrice", [])
        tx = {
            "chainId": self._config.chain_id,
            "nonce": nonce,
            "to": wallet_address,
            "value": value_wei,
            "gas": self._config.gas_limit,
            "gasPrice": gas_price,
            "data": "0x",
        }
        signed = self._account.sign_transaction(tx, self._config.private_key)
        raw_tx = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction", None)
        if raw_tx is None:
            raise RuntimeError("evm_signing_failed_missing_raw_transaction")
        if isinstance(raw_tx, (bytes, bytearray)):
            raw_hex = f"0x{raw_tx.hex()}"
        else:
            raw_hex = str(raw_tx)
            if not raw_hex.startswith("0x"):
                raw_hex = f"0x{raw_hex}"

        tx_hash = await self._rpc("eth_sendRawTransaction", [raw_hex])
        if not isinstance(tx_hash, str) or not tx_hash.startswith("0x"):
            raise RuntimeError("evm_send_failed_invalid_tx_hash")
        return tx_hash

    async def confirm_tx(self, tx_hash: str) -> bool:
        deadline = time.monotonic() + self._config.confirm_timeout_seconds
        while time.monotonic() < deadline:
            receipt = await self._rpc("eth_getTransactionReceipt", [tx_hash])
            if receipt:
                if not isinstance(receipt, dict):
                    return False
                status = self._hex_or_int_to_int(receipt.get("status"))
                if status != 1:
                    return False
                if self._config.min_confirmations <= 1:
                    return True
                block_number = self._hex_or_int_to_int(receipt.get("blockNumber"))
                latest_block = await self._rpc_int("eth_blockNumber", [])
                confirmations = latest_block - block_number + 1
                if confirmations >= self._config.min_confirmations:
                    return True
            await asyncio.sleep(self._config.confirm_poll_seconds)
        return False

    def _load_account(self) -> Any:
        try:
            from eth_account import Account  # type: ignore
        except Exception as exc:  # pragma: no cover - import-time behavior
            raise RuntimeError("missing_dependency_eth_account") from exc
        return Account

    async def _next_nonce(self) -> int:
        if self._next_nonce_value is None:
            self._next_nonce_value = await self._rpc_int("eth_getTransactionCount", [self._sender_address, "pending"])
        nonce = self._next_nonce_value
        self._next_nonce_value += 1
        return nonce

    async def _rpc_int(self, method: str, params: list[Any]) -> int:
        result = await self._rpc(method, params)
        return self._hex_or_int_to_int(result)

    async def _rpc(self, method: str, params: list[Any]) -> Any:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(self._config.rpc_url, json=payload)
            response.raise_for_status()
            body = response.json()

        if not isinstance(body, dict):
            raise RuntimeError("evm_rpc_invalid_response")
        if body.get("error") is not None:
            code = body["error"].get("code") if isinstance(body["error"], dict) else "unknown"
            raise RuntimeError(f"evm_rpc_error:{code}")
        return body.get("result")

    def _decimal_to_wei(self, amount: Decimal) -> int:
        scale = Decimal(10) ** self._config.amount_decimals
        return int((amount * scale).quantize(Decimal("1"), rounding=ROUND_DOWN))

    def _hex_or_int_to_int(self, value: Any) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("0x"):
                return int(raw, 16)
            return int(raw)
        raise RuntimeError("evm_rpc_invalid_numeric_value")
