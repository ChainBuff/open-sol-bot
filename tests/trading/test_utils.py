import pytest
from solbot_common.constants import PUMP_FUN_PROGRAM
from solders.pubkey import Pubkey

from libs.common.solbot_common.utils.utils import (
    get_associated_bonding_curve, get_async_client, get_bonding_curve_account,
    get_bonding_curve_pda, get_global_account)


def test_get_bonding_curve_pda():
    mint = Pubkey.from_string("7YYfWqoKvZmGfX4MgE9TuTpPZz9waHAUUxshFmwqpump")
    result = get_bonding_curve_pda(mint, PUMP_FUN_PROGRAM)
    assert str(result[0]) == "8o4o1rhJQ2AoCHBRvumBAmbPH9pxrxWCAYBCfEFcniee"
    assert result[1] == 255


def test_get_associated_bonding_curve():
    mint = Pubkey.from_string("7YYfWqoKvZmGfX4MgE9TuTpPZz9waHAUUxshFmwqpump")
    bonding_curve = get_bonding_curve_pda(mint, PUMP_FUN_PROGRAM)
    result = get_associated_bonding_curve(bonding_curve[0], mint)
    assert str(result) == "GDmfeokYLpfG4s1MdLcSYTriEgapkBL4hCupMk5UTRev"


@pytest.mark.asyncio
@pytest.mark.parametrize("mint_address,expected_values", [
    ("7YYfWqoKvZmGfX4MgE9TuTpPZz9waHAUUxshFmwqpump", {
        "virtual_token_reserves": 1072999997348202,
        "virtual_sol_reserves": 30000000087,
        "real_token_reserves": 793099997348202,
        "real_sol_reserves": 87,
        "token_total_supply": 1000000000000000,
        "complete": False
    }),
    ("A7S4UkbpAXSVfG196Qvr8TMvpvx3Lz2Q4X2RecuApump", {
        "virtual_token_reserves": 0,
        "virtual_sol_reserves": 0,
        "real_token_reserves": 0,
        "real_sol_reserves": 0,
        "token_total_supply": 1000000000000000,
        "complete": True
    }),
])
async def test_get_bonding_curve_account(mint_address, expected_values):
    client = get_async_client()
    mint = Pubkey.from_string(mint_address)
    result = await get_bonding_curve_account(
        client,
        mint,
        PUMP_FUN_PROGRAM,
    )
    assert result
    bonding_curve, associated_bonding_curve, account = result
    assert account.virtual_token_reserves == expected_values["virtual_token_reserves"]
    assert account.virtual_sol_reserves == expected_values["virtual_sol_reserves"]
    assert account.real_token_reserves == expected_values["real_token_reserves"]
    assert account.real_sol_reserves == expected_values["real_sol_reserves"]
    assert account.token_total_supply == expected_values["token_total_supply"]
    assert account.complete == expected_values["complete"]


@pytest.mark.asyncio
async def test_get_bonding_curve_account_already_launched():
    client = get_async_client()
    mint = Pubkey.from_string("MGj4gwN6f5Mna85uiiWRohwQ2cDHWPHVMMpkeJJpump")
    result = await get_bonding_curve_account(
        client,
        mint,
        PUMP_FUN_PROGRAM,
    )
    assert result
    bonding_curve, associated_bonding_curve, account = result
    assert account.discriminator == 6966180631402821399
    assert account.virtual_token_reserves == 0
    assert account.virtual_sol_reserves == 0
    assert account.real_token_reserves == 0
    assert account.real_sol_reserves == 0
    assert account.token_total_supply == 1000000000000000
    assert account.complete


@pytest.mark.asyncio
async def test_get_global_account():
    client = get_async_client()
    result = await get_global_account(client, PUMP_FUN_PROGRAM)
    assert result
    # GlobalAccount(discriminator=9183522199395952807, initialized=True, authority=Pubkey(
    #     DCpJReAfonSrgohiQbTmKKbjbqVofspFRHz9yQikzooP,
    # ), fee_recipient=Pubkey(
    #     CebN5WGQ4jvEPvsVU4EoHEpgzq1VV7AbicfhtW4xC9iM,
    # ), initial_virtual_token_reserves=1073000000000000, initial_virtual_sol_reserves=30000000000, initial_real_token_reserves=793100000000000, token_total_supply=1000000000000000, fee_basis_points=100)
    assert result.discriminator == 9183522199395952807
    assert result.initialized
    assert str(result.authority) == "DCpJReAfonSrgohiQbTmKKbjbqVofspFRHz9yQikzooP"
    assert str(result.fee_recipient) == "CebN5WGQ4jvEPvsVU4EoHEpgzq1VV7AbicfhtW4xC9iM"
    assert result.initial_virtual_token_reserves == 1073000000000000
    assert result.initial_virtual_sol_reserves == 30000000000
    assert result.initial_real_token_reserves == 793100000000000
    assert result.token_total_supply == 1000000000000000
    assert result.fee_basis_points == 100


@pytest.mark.asyncio
async def test_has_ata():
    client = get_async_client()
    mint = Pubkey.from_string("HiPZWtXxEvgzKnMBfHGvZqHfvgaJ1YHZVhwai1Wd8t4J")
    owner = Pubkey.from_string("Ckwd4awa6N2VWyMuuScbkdEJqSY5VpajuLd7m7QwXMvY")
    result = await has_ata(client, mint, owner)
    assert result is False
