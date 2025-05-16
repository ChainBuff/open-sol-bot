from solbot_cache import AccountAmountCache, MintAccountCache
from solbot_common.constants import (ASSOCIATED_TOKEN_PROGRAM, PUMP_BUY_METHOD,
                                     PUMP_FUN_ACCOUNT, PUMP_FUN_PROGRAM,
                                     PUMP_GLOBAL_ACCOUNT, PUMP_SELL_METHOD,
                                     RENT_PROGRAM_ID, SOL_DECIMAL,
                                     SYSTEM_PROGRAM_ID, TOKEN_PROGRAM_ID, WSOL)
from solbot_common.IDL.pumpfun import PumpFunInterface
from solbot_common.log import logger
from solbot_common.utils.utils import (get_bonding_curve_account,
                                       get_global_account)
from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore
from spl.token.instructions import (CloseAccountParams, close_account,
                                    create_associated_token_account,
                                    get_associated_token_address)
from trading.exceptions import BondingCurveNotFound
from trading.swap import SwapDirection, SwapInType
from trading.tx import build_transaction
from trading.utils import (has_ata, max_amount_with_slippage,
                           min_amount_with_slippage)

from .base import TransactionBuilder


# Reference: https://github.com/wisarmy/raytx/blob/main/src/pump.rs
class PumpTransactionBuilder(TransactionBuilder):
    async def build_swap_transaction(
        self,
        keypair: Keypair,
        token_address: str,
        ui_amount: float,
        swap_direction: SwapDirection,
        slippage_bps: int,
        in_type: SwapInType | None = None,
        use_jito: bool = False,
        priority_fee: float | None = None,
    ) -> VersionedTransaction:
        if swap_direction == "sell" and in_type is None:
            raise ValueError("in_type must be specified when selling")

        owner = keypair.pubkey()
        mint = Pubkey.from_string(token_address)
        program_id = TOKEN_PROGRAM_ID
        native_mint = WSOL

        if swap_direction == SwapDirection.Buy:
            token_in = native_mint
            token_out = mint
            pump_method = PUMP_BUY_METHOD
        elif swap_direction == SwapDirection.Sell:
            token_in = mint
            token_out = native_mint
            pump_method = PUMP_SELL_METHOD
        else:
            raise ValueError("swap_direction must be buy or sell")

        pump_program = PUMP_FUN_PROGRAM
        result = await get_bonding_curve_account(self.rpc_client, mint, pump_program)
        if result is None:
            raise BondingCurveNotFound("bonding curve account not found")
        bonding_curve, associated_bonding_curve, bonding_curve_account = result

        global_account = await get_global_account(self.rpc_client, pump_program)
        if global_account is None:
            raise ValueError("global account not found")

        fee_recipient = global_account.fee_recipient

        in_ata = get_associated_token_address(owner=owner, mint=token_in)
        out_ata = get_associated_token_address(owner=owner, mint=token_out)

        create_instruction = None
        close_instruction = None
        if swap_direction == SwapDirection.Buy:
            # 如果 ata 账户不存在，需要创建
            if not await has_ata(
                self.rpc_client,
                owner,
                token_out,
            ):
                create_instruction = create_associated_token_account(owner, owner, token_out)

            amount_specified = int(ui_amount * SOL_DECIMAL)
        elif swap_direction == SwapDirection.Sell:
            in_amount = await AccountAmountCache().get_amount(in_ata)
            in_mint = await MintAccountCache().get_mint_account(token_in)
            if in_mint is None:
                raise Exception("in_mint not found")

            if in_type == SwapInType.Pct:
                amount_in_pct = min(ui_amount, 1)
                if amount_in_pct < 0:
                    raise Exception("amount_in_pct must be greater than 0, range [0, 1]")

                if amount_in_pct == 1:
                    # sell all, close ata
                    logger.info(f"Sell all, will be close ATA for mint {token_in}")
                    close_instruction = close_account(
                        CloseAccountParams(
                            program_id=program_id,
                            account=in_ata,
                            dest=owner,
                            owner=owner,
                        )
                    )
                    amount_specified = in_amount
                else:
                    amount_specified = int(in_amount * amount_in_pct)
            elif in_type == SwapInType.Qty:
                amount_specified = int(ui_amount * 10**in_mint.decimals)
            else:
                raise Exception("in_type must be qty or pct")

        logger.info(f"swap: {token_in}, value: {amount_specified} -> {token_out}")

        # calculate tokens out
        unit_price = (
            bonding_curve_account.virtual_sol_reserves
            / bonding_curve_account.virtual_token_reserves
            / 1000
        )

        if swap_direction == SwapDirection.Buy:
            max_sol_cost = max_amount_with_slippage(amount_specified, slippage_bps)
            sol_amount_threshold = max_sol_cost
            token_amount = (
                amount_specified
                * bonding_curve_account.virtual_token_reserves
                // bonding_curve_account.virtual_sol_reserves
            )
            input_accounts = {
                "fee_recipient": fee_recipient,
                "mint": mint,
                "bonding_curve": bonding_curve,
                "associated_bonding_curve": associated_bonding_curve,
                "associated_user": out_ata,
                "user": owner,
                "global": PUMP_GLOBAL_ACCOUNT,
                "system_program": SYSTEM_PROGRAM_ID,
                "token_program": TOKEN_PROGRAM_ID,
                "rent": RENT_PROGRAM_ID,
                "event_authority": PUMP_FUN_ACCOUNT,
                "program": PUMP_FUN_PROGRAM,
            }
        elif swap_direction == SwapDirection.Sell:
            sol_output = (
                amount_specified
                * bonding_curve_account.virtual_sol_reserves
                // bonding_curve_account.virtual_token_reserves
            )
            min_sol_cost = min_amount_with_slippage(sol_output, slippage_bps)
            sol_amount_threshold = min_sol_cost
            token_amount = amount_specified
            input_accounts = {
                "fee_recipient": fee_recipient,
                "mint": mint,
                "bonding_curve": bonding_curve,
                "associated_bonding_curve": associated_bonding_curve,
                "associated_user": in_ata,
                "user": owner,
                "global": PUMP_GLOBAL_ACCOUNT,
                "system_program": SYSTEM_PROGRAM_ID,
                "token_program": TOKEN_PROGRAM_ID,
                "associated_token_program": ASSOCIATED_TOKEN_PROGRAM,
                "rent": RENT_PROGRAM_ID,
                "event_authority": PUMP_FUN_ACCOUNT,
                "program": PUMP_FUN_PROGRAM,
            }

        logger.info(
            f"token_amount: {token_amount}, sol_amount_threshold: {sol_amount_threshold}, unit_price: {unit_price}"
        )

        instructions = []
        pumpfun = PumpFunInterface(keypair, self.rpc_client)
        pump_method = pumpfun.program.methods[swap_direction]
        build_swap_instruction = (
            pump_method.args([token_amount, sol_amount_threshold])
            .accounts(input_accounts)
            .instruction()
        )
        logger.debug(f"Build swap input accounts: {input_accounts}")

        if create_instruction is not None:
            instructions.append(create_instruction)
            logger.debug(f"Create instruction: {create_instruction}")
        if amount_specified > 0:
            instructions.append(build_swap_instruction)
            logger.debug(f"Swap instruction: {build_swap_instruction}")
        if close_instruction is not None:
            instructions.append(close_instruction)
            logger.debug(f"Close instruction: {close_instruction}")

        if len(instructions) == 0:
            raise Exception("instructions is empty")

        logger.debug(f"Swap instructions: {instructions}")

        return await build_transaction(
            keypair=keypair,
            instructions=instructions,
            priority_fee=priority_fee,
            use_jito=use_jito,
        )
