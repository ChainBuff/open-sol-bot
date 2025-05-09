import os

import pytest
#from trading.utils import get_async_client
from solbot_common.utils import get_async_client
from solders.keypair import Keypair

#from trading.swap import SwapDirection

#from trading.swap_protocols.pump import Pump


@pytest.mark.asyncio
@pytest.mark.skip(reason="Pump class seems to be removed")
async def test_swap_buy():
    client = get_async_client()

    keypair = Keypair.from_base58_string(os.environ["KEYPAIR"])
    pump = Pump(client)
    mint = "G1WcqfZxkZGHvPLRvbSpVDgzsWxuWxbi1GcufwcHpump"
    amount_in = 0.0001
    swap_direction = SwapDirection.Buy
    slippage = 1000
    sig = await pump.swap(keypair, mint, amount_in, swap_direction, slippage)
    print(sig)


# @pytest.mark.asyncio
# async def test_swap_sell_qty():
#     client = await get_async_client()

#     pump = Pump(client, settings.wallet.keypair)
#     mint = "HiPZWtXxEvgzKnMBfHGvZqHfvgaJ1YHZVhwai1Wd8t4J"
#     amount_in = 100000
#     swap_direction = "sell"
#     in_type = SwapInType.Qty
#     slippage = 10
#     sig = await pump.swap(mint, amount_in, swap_direction, slippage, in_type)
#     assert sig is not None


# @pytest.mark.asyncio
# async def test_swap_sell_pct():
#     client = get_async_client()

#     pump = Pump(client, settings.wallet.keypair)
#     mint = "HiPZWtXxEvgzKnMBfHGvZqHfvgaJ1YHZVhwai1Wd8t4J"
#     amount_in = 0.01  # 1%
#     swap_direction = "sell"
#     in_type = SwapInType.Pct
#     slippage = 10
#     sig = await pump.swap(mint, amount_in, swap_direction, slippage, in_type)
#     assert sig is not None
#     raise NotImplementedError
