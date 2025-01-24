import httpx
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from solders.keypair import Keypair  # type: ignore
from solders.rpc.responses import RpcSimulateTransactionResult  # type: ignore
from solders.signature import Signature  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore

from cache.token_info import TokenInfoCache
from common.config import settings
from common.constants import SOL_DECIMAL, WSOL
from trading.swap import SwapDirection, SwapInType
from trading.tx import sign_transaction_from_raw

from .proto import TraderProtocol


class Gmgn(TraderProtocol):
    def __init__(self, rpc_client: AsyncClient) -> None:
        self.client = httpx.AsyncClient(base_url="https://gmgn.ai")
        self.api_path = "/defi/router/v1/sol/tx/get_swap_route"
        self.rpc_client = rpc_client
        self.token_info_cache = TokenInfoCache()

    async def build_swap_transaction(
        self,
        keypair: Keypair,
        token_address: str,
        ui_amount: float,
        swap_direction: SwapDirection,
        slippage_bps: int,
        in_type: SwapInType | None = None,
        use_jito: bool = False,
    ) -> VersionedTransaction:
        """Build swap transaction with GMGN API.

        Args:
            token_address (str): token address
            amount_in (float): amount in
            swap_direction (SwapDirection): swap direction
            slippage (int): slippage, percentage
            in_type (SwapInType | None, optional): in type. Defaults to None.
            use_jto (bool, optional): use jto. Defaults to False.

        Returns:
            VersionedTransaction: The built transaction ready to be signed and sent
        """
        if swap_direction == "sell" and in_type is None:
            raise ValueError("in_type must be specified when selling")

        if swap_direction == SwapDirection.Buy:
            token_in = str(WSOL)
            token_out = token_address
            swap_mode = "ExactIn"
            amount = str(int(ui_amount * SOL_DECIMAL))
        elif swap_direction == SwapDirection.Sell:
            token_info = await self.token_info_cache.get(token_address)
            if token_info is None:
                raise ValueError("Token info not found")
            decimals = token_info.decimals
            token_in = token_address
            token_out = str(WSOL)
            swap_mode = "ExactOut"
            amount = str(int(ui_amount * 10**decimals))
        else:
            raise ValueError("swap_direction must be buy or sell")

        fee = settings.trading.unit_limit * settings.trading.unit_price / 10**15
        slippage = slippage_bps / 100
        params = {
            "token_in_address": token_in,
            "token_out_address": token_out,
            "in_amount": amount,
            "from_address": keypair.pubkey().__str__(),
            "slippage": slippage,
            "swap_mode": swap_mode,
            "fee": fee,
        }

        # TODO: 获取报价解耦
        resp = await self.client.get(self.api_path, params=params)
        resp.raise_for_status()

        js = resp.json()
        if js["code"] != 0:
            raise Exception("Error: {}, Argument: {}".format(js["msg"], params))

        data = js["data"]
        raw_tx = data["raw_tx"]
        swap_tx = raw_tx["swapTransaction"]

        signed_tx = await sign_transaction_from_raw(swap_tx, keypair)
        return signed_tx

    async def send_transaction(self, transaction: VersionedTransaction) -> Signature:
        """Send a signed transaction.

        Args:
            transaction (VersionedTransaction): The signed transaction to send

        Returns:
            Signature: The transaction signature
        """
        resp = await self.rpc_client.send_transaction(
            transaction,
            opts=TxOpts(skip_preflight=not settings.trading.preflight_check),
        )
        return resp.value

    async def simulate_transaction(
        self, transaction: VersionedTransaction
    ) -> RpcSimulateTransactionResult:
        """Simulate a signed transaction.

        Args:
            transaction (VersionedTransaction): The signed transaction to simulate

        Returns:
            SimulationResult: The simulation result
        """
        resp = await self.rpc_client.simulate_transaction(transaction)
        return resp.value

    async def swap(
        self,
        keypair: Keypair,
        token_address: str,
        ui_amount: float,
        swap_direction: SwapDirection,
        slippage_bps: int,
        in_type: SwapInType | None = None,
        use_jito: bool = False,
    ) -> Signature | None:
        """Swap token with GMGN API.

        Args:
            token_address (str): token address
            amount_in (float): amount in
            swap_direction (Literal["buy", "sell"]): swap direction
            slippage (int): slippage, percentage
            in_type (SwapInType | None, optional): in type. Defaults to None.
            use_jto (bool, optional): use jto. Defaults to False.
        """
        transaction = await self.build_swap_transaction(
            keypair=keypair,
            token_address=token_address,
            ui_amount=ui_amount,
            swap_direction=swap_direction,
            slippage_bps=slippage_bps,
            in_type=in_type,
            use_jito=use_jito,
        )
        if settings.trading.tx_simulate:
            await self.simulate_transaction(transaction)
            return
        else:
            return await self.send_transaction(transaction)
