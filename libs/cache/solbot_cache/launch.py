from solbot_common.constants import PUMP_FUN_PROGRAM
from solbot_common.utils.utils import (get_async_client,
                                       get_bonding_curve_account)
from solders.pubkey import Pubkey  # type: ignore

from .cached import cached


class LaunchCache:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        self.client = get_async_client()

    def __repr__(self) -> str:
        return "LaunchCache()"

    @cached(ttl=None, noself=True)
    async def is_pump_token_launched(self, mint: str | Pubkey) -> bool:
        """检查 pump 代币是否已被发射。

        通过检查代币的 virtual_sol_reserves 是否为 0 来判断。
        如果为 0，说明代币已经在 Raydium 上发射。

        Args:
            mint (str): 代币的 mint 地址

        Returns:
            bool: 如果代币已发射返回 True，否则返回 False

        Raises:
            BondingCurveNotFound: 如果找不到对应的 bonding curve 账户
        """
        result = await get_bonding_curve_account(
            self.client,
            Pubkey.from_string(mint) if isinstance(mint, str) else mint,
            PUMP_FUN_PROGRAM,
        )
        if result is None:
            return False
        _, _, bonding_curve_account = result
        return bonding_curve_account.virtual_sol_reserves == 0
