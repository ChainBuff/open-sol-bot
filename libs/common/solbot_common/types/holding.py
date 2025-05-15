from dataclasses import dataclass


@dataclass
class HoldingToken:
    mint: str
    balance: float
    balance_str: str  # 带有单位的余额
    symbol: str
    # usd_value: float
    # price: float
    # total_profit: float = 0
    # total_profit_pnl: float = 0
    # last_active_timestamp: int | None = None


@dataclass
class TokenAccountBalance:
    balance: float
    decimals: int
    
    @property
    def is_zero(self) -> bool:
        """判断余额是否为 0"""
        return self.balance == 0
