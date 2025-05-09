import pytest
from solana.rpc.async_api import AsyncClient
from solbot_common.config import settings

#from trading.swap_protocols import RayV4


@pytest.fixture(autouse=True, scope="module")
def ray_v4():
    # client = AsyncClient("https://api.mainnet-beta.solana.com")
    client = AsyncClient(f"https://rpc.shyft.to?api_key={settings.api.shyft_api_key}")
    return RayV4(client)


@pytest.mark.asyncio
@pytest.mark.skip(reason="RayV4 class seems to be removed")
async def test_build_buy_instructions_with_token_mint(ray_v4): #: RayV4):
    """
    测试提供 token mint 去构建交易
    """
    token_mint = "2ru87k7yAZnDRsnqVpgJYETFgqVApuBcwB2xDb19pump"
    payer_keypair = settings.wallet.keypair
    instructions = await ray_v4.build_buy_instructions(
        payer_keypair=payer_keypair,
        token_address=token_mint,
        sol_in=0.1,
        slippage_bps=10,
    )
    print(instructions)
    assert len(instructions) > 0


# @pytest.mark.asyncio
# async def test_buy_with_ray_v4_raises_error_when_pool_not_found(ray_v4: RayV4):
#     """
#     Test that attempting to buy with an invalid token address raises ValueError
#     """
#     payer_keypair = settings.wallet.keypair

#     # Use pytest.raises to verify that ValueError is raised
#     with pytest.raises(ValueError, match="Error fetching pool keys"):
#         await ray_v4.build_buy_instructions(
#             payer_keypair=payer_keypair,
#             token_address="3CSeAGiw5TYeuZfB74adUM1M9if1fEDXzr5PrnuNpump",
#             sol_in=0.1,
#             slippage_bps=10,
#         )
