import pytest
from solders.signature import Signature
from wallet_tracker.wss.tx_detail_fetcher import TxDetailRawFetcher


@pytest.mark.asyncio
async def test_raw_fetcher():
    fetcher = TxDetailRawFetcher()
    signature = (
        "f3rM4XSC4fNyNttzQAbePJFeKotmhrNoALDvtSYUwXJP5QqSKqUGh1msjR3YeaMu5aeCbXfhd2bwNQymvUv5ZBs"
    )
    tx_detail = await fetcher.fetch(Signature.from_string(signature))
    print(tx_detail)
    assert tx_detail
    assert tx_detail["transaction"]["signatures"][0] == signature
