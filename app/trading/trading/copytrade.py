"""跟单交易

订阅 tx_event 事件，并将其转为 swap_event 事件
"""

import asyncio
from typing import Literal

from solbot_common.constants import SOL_DECIMAL, WSOL
from solbot_common.cp.copytrade_event import NotifyCopyTradeProducer
from solbot_common.cp.swap_event import SwapEventProducer
from solbot_common.cp.tx_event import TxEventConsumer
from solbot_common.log import logger
from solbot_common.models.tg_bot.copytrade import CopyTrade
from solbot_common.types.swap import SwapEvent
from solbot_common.types.tx import TxEvent, TxType
from solbot_common.utils import calculate_auto_slippage
from solbot_db.redis import RedisClient
from solbot_services.bot_setting import BotSettingService as SettingService
from solbot_services.copytrade import CopyTradeService
from solbot_services.holding import HoldingService

IGNORED_MINTS = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",  # mSOL
}


class CopyTradeProcessor:
    """跟单交易"""

    def __init__(self):
        redis_client = RedisClient.get_instance()
        self.tx_event_consumer = TxEventConsumer(
            redis_client,
            "trading:tx_event",
            "trading:new_swap_event",
        )
        self.tx_event_consumer.register_callback(self._process_tx_event)
        self.copytrade_service = CopyTradeService()
        self.setting_service = SettingService()
        self.holding_service = HoldingService()
        self.swap_event_producer = SwapEventProducer(redis_client)
        self.notify_copytrade_producer = NotifyCopyTradeProducer(redis_client)

    async def _process_tx_event(self, tx_event: TxEvent):
        """处理交易事件"""
        logger.info(f"Processing tx event: {tx_event}")
        copytrade_items = await self.copytrade_service.get_by_target_wallet(tx_event.who)
        swap_mode = "ExactIn" if tx_event.tx_direction == "buy" else "ExactOut"
        # buy_pct = 0
        sell_pct = 0
        if swap_mode == "ExactIn":
            input_mint = WSOL.__str__()
            output_mint = tx_event.mint
            # buy_pct = round(
            #     (tx_event.post_token_amount - tx_event.pre_token_amount)
            #     / tx_event.post_token_amount,
            #     4,
            # )
        else:
            input_mint = tx_event.mint
            output_mint = WSOL.__str__()
            # 卖出比例
            if tx_event.tx_type == TxType.CLOSE_POSITION:
                sell_pct = 1
            else:
                sell_pct = round(
                    (tx_event.pre_token_amount - tx_event.post_token_amount)
                    / tx_event.pre_token_amount,
                    4,
                )
        program_id = tx_event.program_id
        timestamp = tx_event.timestamp

        tasks = []
        for copytrade in copytrade_items:
            coro = self._process_copytrade(
                swap_mode=swap_mode,
                tx_event=tx_event,
                program_id=program_id,
                sell_pct=sell_pct,
                input_mint=input_mint,
                output_mint=output_mint,
                timestamp=timestamp,
                copytrade=copytrade,
            )
            tasks.append(coro)

        await asyncio.gather(*tasks)

    async def _process_copytrade(
        self,
        swap_mode: Literal["ExactIn", "ExactOut"],
        tx_event: TxEvent,
        program_id: str | None,
        sell_pct: float,
        input_mint: str,
        output_mint: str,
        timestamp: int,
        copytrade: CopyTrade,
    ):
        if input_mint in IGNORED_MINTS or output_mint in IGNORED_MINTS:
            logger.info(f"Skipping swap due to ignored mint: {input_mint} {output_mint}")
            return

        try:
            # 根据不同的根据设置，创建不同的 swap_event
            setting = await self.setting_service.get(copytrade.chat_id, copytrade.owner)
            if setting is None:
                raise ValueError(
                    f"Setting not found, chat_id: {copytrade.chat_id}, wallet: {copytrade.owner}"
                )

            if swap_mode == "ExactIn":
                if copytrade.is_fixed_buy:
                    ui_amount = copytrade.fixed_buy_amount
                    if ui_amount is None:
                        raise ValueError("fixed_buy_amount is None")
                    amount = int(ui_amount * SOL_DECIMAL)
                elif copytrade.auto_follow:
                    # TODO: 跟随买入
                    raise NotImplementedError("auto_follow")
                else:
                    raise AssertionError("not possible")
            else:
                # 获取当前持仓的数量
                balance = await self.holding_service.get_token_account_balance(
                    mint=tx_event.mint,
                    wallet=copytrade.owner,
                )
                if balance.is_zero:
                    logger.info(f"No holdings for {tx_event.mint}, skip...")
                    return

                # 自动跟买跟卖
                if copytrade.auto_follow:
                    amount = int(int(balance.balance * balance.decimals) * sell_pct)
                    ui_amount = amount / balance.decimals
                else:
                    logger.info("Not auto follow, skip...")
                    return

            if copytrade.anti_sandwich:
                slippage_bps = setting.sandwich_slippage_bps
            elif copytrade.auto_slippage is False:
                slippage_bps = copytrade.custom_slippage_bps
            else:
                slippage_bps = await calculate_auto_slippage(
                    input_mint=input_mint,
                    output_mint=output_mint,
                    amount=amount,
                    swap_mode=swap_mode,
                )

            if swap_mode == "ExactOut":
                amount_pct = sell_pct
                swap_in_type = "pct"
            else:
                amount_pct = None
                swap_in_type = "qty"

            priority_fee = copytrade.priority
            swap_event = SwapEvent(
                user_pubkey=copytrade.owner,
                swap_mode=swap_mode,
                input_mint=input_mint,
                output_mint=output_mint,
                amount=amount,
                ui_amount=ui_amount,
                slippage_bps=slippage_bps,
                timestamp=timestamp,
                priority_fee=priority_fee,
                program_id=program_id,
                amount_pct=amount_pct,
                swap_in_type=swap_in_type,
                by="copytrade",
                tx_event=tx_event,
            )
            # PERF: 理论上,这两个 producer 是重复的
            # 只需要在 consumer 处, 使用不同的消费组即可
            await self.swap_event_producer.produce(swap_event=swap_event)
            await self.notify_copytrade_producer.produce(data=swap_event)
            logger.info(f"New Copy Trade: {swap_event}")
        except Exception as e:
            logger.exception(f"Failed to process copytrade: {e}")
            # TODO: 通知到用户，跟单交易失败

    async def start(self):
        """启动跟单交易"""
        await self.tx_event_consumer.start()

    def stop(self):
        """停止跟单交易"""
        self.tx_event_consumer.stop()
