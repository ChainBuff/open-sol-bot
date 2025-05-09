import struct
from typing import Final

from construct import Flag, Int64ul, Struct


class BondingCurveError(Exception):
    """Exception raised for errors in bonding curve account data validation."""
    pass

# See: https://github.com/chainstacklabs/pump-fun-bot/blob/main/learning-examples/bonding-curve-progress/get_bonding_curve_status.py
BONDING_CURVE_ACCOUNT_LAYOUT = Struct(
    "virtual_token_reserves" / Int64ul,
    "virtual_sol_reserves" / Int64ul,
    "real_token_reserves" / Int64ul,
    "real_sol_reserves" / Int64ul,
    "token_total_supply" / Int64ul,
    "complete" / Flag,
)
_EXPECTED_DISCRIMINATOR: Final[bytes] = struct.pack("<Q", 6966180631402821399)

class BondingCurveAccount:
    """ 
    Represents the state of a bonding curve account.
    
    Attributes:
        virtual_token_reserves: Virtual token reserves in the curve
        virtual_sol_reserves: Virtual SOL reserves in the curve
        real_token_reserves: Real token reserves in the curve
        real_sol_reserves: Real SOL reserves in the curve
        token_total_supply: Total token supply in the curve
        complete: Whether the curve has completed and liquidity migrated
    """
    def __init__(self, data: bytes) -> None:
        if data[:8] != _EXPECTED_DISCRIMINATOR:
            raise ValueError("Invalid curve state discriminator")

        parsed = BONDING_CURVE_ACCOUNT_LAYOUT.parse(data[8:])
        self.__dict__.update(parsed)

    virtual_token_reserves: int
    virtual_sol_reserves: int
    real_token_reserves: int
    real_sol_reserves: int
    token_total_supply: int
    complete: bool

    def get_buy_price(self, amount: int) -> int:
        if self.complete:
            raise BondingCurveError("Curve is complete")

        if amount <= 0:
            return 0

        # Calculate the product of virtual reserves
        n = self.virtual_sol_reserves * self.virtual_token_reserves

        # Calculate the new virtual sol reserves after the purchase
        i = self.virtual_sol_reserves + amount

        # Calculate the new virtual token reserves after the purchase
        r = n // i + 1

        # Calculate the amount of tokens to be purchased
        s = self.virtual_token_reserves - r

        # Return the minimum of the calculated tokens and real token reserves
        return min(s, self.real_token_reserves)

    def get_sell_price(self, amount: int, fee_basis_points: int) -> int:
        if self.complete:
            raise BondingCurveError("Curve is complete")

        if amount <= 0:
            return 0

        # Calculate the proportional amount of virtual sol reserves to be received
        n = (amount * self.virtual_sol_reserves) // (self.virtual_token_reserves + amount)

        # Calculate the fee amount in the same units
        a = (n * fee_basis_points) // 10000

        # Return the net amount after deducting the fee
        return n - a

    def get_market_cap_sol(self) -> int:
        if self.virtual_token_reserves == 0:
            return 0

        return (self.token_total_supply * self.virtual_sol_reserves) // self.virtual_token_reserves

    def get_final_market_cap_sol(self, fee_basis_points: int) -> int:
        total_sell_value = self.get_buy_out_price(self.real_token_reserves, fee_basis_points)
        total_virtual_value = self.virtual_sol_reserves + total_sell_value
        total_virtual_tokens = self.virtual_token_reserves - self.real_token_reserves

        if total_virtual_tokens == 0:
            return 0

        return (self.token_total_supply * total_virtual_value) // total_virtual_tokens

    def get_buy_out_price(self, amount: int, fee_basis_points: int) -> int:
        sol_tokens = self.real_sol_reserves if amount < self.real_sol_reserves else amount
        total_sell_value = (sol_tokens * self.virtual_sol_reserves) // (
            self.virtual_token_reserves - sol_tokens
        ) + 1
        fee = (total_sell_value * fee_basis_points) // 10000
        return total_sell_value + fee

    # @classmethod
    # def from_buffer(cls, buffer: bytes) -> "BondingCurveAccount":
    #     """
    #     从字节缓冲区解析账户数据
    #     格式: <Q Q Q Q Q Q ?
    #     Q: unsigned long long (8 bytes)
    #     ?: boolean (1 byte)
    #     """
    #     try:
    #         return cls(buffer)
    #     except struct.error as e:
    #         raise BondingCurveError(f"Failed to decode buffer: {e}")
