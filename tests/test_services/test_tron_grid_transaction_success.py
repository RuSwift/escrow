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


def test_describe_trx_resource_failure_out_of_energy():
    s = TronGridClient.describe_trx_resource_failure(
        {"receipt": {"result": "OUT_OF_ENERGY"}}, None
    )
    assert s is not None
    assert "OUT_OF_ENERGY" in s
    assert "энерг" in s.lower() or "TRX" in s


def test_build_transaction_failure_message_revert_trc20():
    info = {
        "id": "0f24fc365f97ac3506b19022c7bc76f61b690578581ed15cb9c0146dd4f6da99",
        "receipt": {"result": "REVERT", "energy_usage_total": 8624},
        "resMessage": "524556455254206f70636f6465206578656375746564",
        "result": "FAILED",
        "contract_address": "41a614f803b6fd780986a42c78ec9c7f77e6ded13c",
    }
    msg = TronGridClient.build_transaction_failure_message(info, None)
    assert "REVERT" in msg
    assert "REVERT opcode executed" in msg
    assert "TRC-20" in msg or "токена" in msg


@pytest.mark.asyncio
async def test_get_transaction_failure_detail_fetches_txwrap_when_receipt_result_missing():
    settings = Settings()
    async with TronGridClient(settings=settings) as client:

        async def mock_post(path: str, payload: dict, **kw):  # type: ignore[no-untyped-def]
            if "gettransactioninfobyid" in path:
                return {
                    "id": "x",
                    "blockNumber": 1,
                    "receipt": {"net_usage": 1},
                    "resMessage": "524556455254206f70636f6465206578656375746564",
                }
            if "gettransactionbyid" in path:
                return {"ret": [{"contractRet": "REVERT"}]}
            raise AssertionError(f"unexpected path {path}")

        client.post = mock_post  # type: ignore[method-assign]
        out = await client.get_transaction_failure_detail("x")
        assert "contractRet" in out
        assert "REVERT opcode executed" in out
