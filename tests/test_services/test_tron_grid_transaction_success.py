"""get_transaction_success: TVM receipt.result vs нативный TRX (contractRet)."""

from __future__ import annotations

import pytest

from services.tron.grid_client import TronGridClient
from settings import Settings


@pytest.mark.asyncio
async def test_get_transaction_success_from_receipt_result():
    settings = Settings()
    async with TronGridClient(settings=settings) as client:

        async def mock_post(path: str, payload: dict, **kw):  # type: ignore[no-untyped-def]
            if "gettransactioninfobyid" in path:
                return {
                    "id": "abc",
                    "blockNumber": 1,
                    "receipt": {"result": "SUCCESS"},
                }
            raise AssertionError(f"unexpected path {path}")

        client.post = mock_post  # type: ignore[method-assign]
        assert await client.get_transaction_success("abc") is True


@pytest.mark.asyncio
async def test_get_transaction_success_native_transfer_uses_gettransactionbyid():
    settings = Settings()
    async with TronGridClient(settings=settings) as client:

        async def mock_post(path: str, payload: dict, **kw):  # type: ignore[no-untyped-def]
            if "gettransactioninfobyid" in path:
                return {
                    "id": "a61def",
                    "blockNumber": 81409161,
                    "receipt": {"net_usage": 268},
                }
            if "gettransactionbyid" in path:
                return {"ret": [{"contractRet": "SUCCESS"}]}
            raise AssertionError(f"unexpected path {path}")

        client.post = mock_post  # type: ignore[method-assign]
        assert await client.get_transaction_success("a61def") is True


@pytest.mark.asyncio
async def test_get_transaction_success_native_transfer_revert():
    settings = Settings()
    async with TronGridClient(settings=settings) as client:

        async def mock_post(path: str, payload: dict, **kw):  # type: ignore[no-untyped-def]
            if "gettransactioninfobyid" in path:
                return {
                    "id": "dead",
                    "blockNumber": 2,
                    "receipt": {"energy_usage": 1},
                }
            if "gettransactionbyid" in path:
                return {"ret": [{"contractRet": "REVERT"}]}
            raise AssertionError(f"unexpected path {path}")

        client.post = mock_post  # type: ignore[method-assign]
        assert await client.get_transaction_success("dead") is False
