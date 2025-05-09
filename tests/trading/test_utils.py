import pytest
from solbot_common.constants import PUMP_FUN_PROGRAM
from solders.pubkey import Pubkey

from libs.common.solbot_common.utils.utils import (
    get_associated_bonding_curve, get_async_client, get_bonding_curve_account,
    get_bonding_curve_pda, get_global_account)


def test_get_bonding_curve_pda():
    mint = Pubkey.from_string("7YYfWqoKvZmGfX4MgE9TuTpPZz9waHAUUxshFmwqpump")
    result = get_bonding_curve_pda(mint, PUMP_FUN_PROGRAM)
    assert str(result) == "8o4o1rhJQ2AoCHBRvumBAmbPH9pxrxWCAYBCfEFcniee"


def test_get_associated_bonding_curve():
    mint = Pubkey.from_string("7YYfWqoKvZmGfX4MgE9TuTpPZz9waHAUUxshFmwqpump")
    bonding_curve = get_bonding_curve_pda(mint, PUMP_FUN_PROGRAM)
    result = get_associated_bonding_curve(bonding_curve, mint)
    assert str(result) == "GDmfeokYLpfG4s1MdLcSYTriEgapkBL4hCupMk5UTRev"


@pytest.mark.asyncio
async def test_get_bonding_curve_account():
    client = get_async_client()
    mint = Pubkey.from_string("7YYfWqoKvZmGfX4MgE9TuTpPZz9waHAUUxshFmwqpump")
    result = await get_bonding_curve_account(
        client,
        mint,
        PUMP_FUN_PROGRAM,
    )
    assert result
    bonding_curve, associated_bonding_curve, account = result
    assert account.discriminator == 6966180631402821399
    assert account.virtual_token_reserves == 1072999997348202
    assert account.virtual_sol_reserves == 30000000087
    assert account.real_token_reserves == 793099997348202
    assert account.real_sol_reserves == 87
    assert account.token_total_supply == 1000000000000000
    assert not account.complete


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
