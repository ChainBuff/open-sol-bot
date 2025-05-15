from decimal import Decimal
from functools import cache

from jupiter_python_sdk.jupiter import Jupiter
from loguru import logger
from solana.rpc.api import Client
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.signature import Signature  # type: ignore
from solders.transaction_status import TransactionConfirmationStatus  # type: ignore
from spl.token.instructions import get_associated_token_address

from solbot_common.layouts.bonding_curve_account import BondingCurveAccount
from solbot_common.layouts.global_account import GlobalAccount
from solbot_common.layouts.mint_account import MintAccount


def get_bonding_curve_pda(mint: Pubkey, program: Pubkey) -> Pubkey:
    return Pubkey.find_program_address([b"bonding-curve", bytes(mint)], program)[0]


async def get_bonding_curve_account(
    client: AsyncClient, mint: Pubkey, program: Pubkey
) -> tuple[Pubkey, Pubkey, BondingCurveAccount] | None:
    bonding_curve = get_bonding_curve_pda(mint, program)
    associated_bonding_curve = get_associated_token_address(bonding_curve, mint)

    account_info = await client.get_account_info_json_parsed(bonding_curve)
    if account_info is None:
        return None
    value = account_info.value
    if value is None:
        return None
    bonding_curve_account = BondingCurveAccount.from_buffer(bytes(value.data))
    return (bonding_curve, associated_bonding_curve, bonding_curve_account)


async def get_global_account(client: AsyncClient, program: Pubkey) -> GlobalAccount | None:
    from solbot_cache.account import GlobalAccountCache

    return await GlobalAccountCache(client).get(program)


def get_associated_bonding_curve(bonding_curve: Pubkey, mint: Pubkey) -> Pubkey:
    return get_associated_token_address(bonding_curve, mint)


@cache
def get_client() -> Client:
    """获取 Solana RPC 客户端

    Returns:
        Client: Solana RPC 客户端
    """
    from solbot_common.config import settings

    return Client(settings.rpc.rpc_url)


@cache
def get_async_client() -> AsyncClient:
    """获取 Solana RPC 客户端

    Returns:
        Client: Solana RPC 客户端
    """
    from solbot_common.config import settings

    return AsyncClient(settings.rpc.rpc_url)


def get_jupiter_client() -> Jupiter:
    rpc_client = get_async_client()
    jupiter = Jupiter(async_client=rpc_client, keypair=Keypair())
    return jupiter


async def validate_transaction(
    tx_hash: str | Signature, client: AsyncClient | None = None
) -> bool | None:
    """验证交易是否已经上链

    Args:
        tx_hash (str): 交易 hash
        client (AsyncClient): Solana RPC 客户端

    Returns:
        Optional[bool]: None 表示未找到交易或者交易尚未上链，True 表示交易已上链，False 表示交易上链失败
    """
    if client is None:
        client = get_async_client()
    if isinstance(tx_hash, str):
        tx_hash = Signature.from_string(tx_hash)
    response = await client.get_signature_statuses([tx_hash], search_transaction_history=True)
    value = response.value[0]
    if value is None:
        return None
    if value.confirmation_status == TransactionConfirmationStatus.Confirmed:
        return value.err is None
    return None


async def get_mint_account(mint: Pubkey, client: AsyncClient) -> MintAccount | None:
    response = await client.get_account_info(mint)
    account = response.value
    if account is None:
        return None
    mint_account = MintAccount.from_buffer(account.data)
    return mint_account


def keypair_to_private_key(keypair: Keypair) -> str:
    """
    将 Solana Keypair 转换为可导入 Phantom 钱包的私钥字符串
    :param keypair: Solana Keypair 对象
    :return: base58 编码的私钥字符串（88位）
    """
    from base58 import b58encode

    # 获取完整的密钥对字节（64字节）
    keypair_bytes = bytes(keypair.to_bytes())
    return b58encode(keypair_bytes).decode("ascii")


def format_number(value: float) -> str:
    """将浮点数转换为带单位的字符串表示

    Args:
        value (float): 需要转换的数值

    Returns:
        str: 带单位的字符串，例如 1K, 10K, 1M, 1B 等

    Examples:
        >>> format_number(1000)
        '1K'
        >>> format_number(10000)
        '10K'
        >>> format_number(1000000)
        '1M'
        >>> format_number(1000000000)
        '1B'
    """
    abs_value = abs(value)
    if abs_value >= 1000000000:
        return f"{value / 1000000000:.2f}B"
    elif abs_value >= 1000000:
        return f"{value / 1000000:.2f}M"
    elif abs_value >= 1000:
        return f"{value / 1000:.2f}K"
    else:
        return f"{value:.2f}"


async def get_token_balance(token_account: Pubkey, client: AsyncClient) -> float | None:
    """获取代币账户余额

    Args:
        token_account (Pubkey): 代币账户
        client (AsyncClient): Solana RPC 客户端

    Returns:
        float | None: 代币账户余额
    """
    resp = await client.get_token_account_balance(token_account)
    return resp.value.ui_amount


# FIXME: jupiter 的报价 API 有请求频率的限制
#  后续需要重构该函数为独立的模块，并使用令牌桶来限制请求频率
#  每秒最多 1 次，每分钟最多 60 次，每小时最多 3600 次
#  否则会报错：429 Too Many Requests
async def calculate_auto_slippage(
    input_mint: str,
    output_mint: str,
    amount: int,
    swap_mode: str = "ExactIn",  # or "ExactOut"
    min_slippage_bps: int = 250,
    max_slippage_bps: int = 3000,
    price_impact_multiplier: float = 1.5,
    default_slippage_bps: int = 500,
) -> int:
    """计算自动滑点，返回 bps

    基于 price impact 动态计算滑点：
    1. price impact 是 0~1 的小数
    2. 基础滑点为 price impact * 100 的 1.5 倍（百分比）
    3. 最小滑点为 250bps， 最大滑点为 3000bps

    Args:
        input_mint (str): 输入代币的 mint 地址
        output_mint (str): 输出代币的 mint 地址
        amount (int): 金额（以最小单位计）
        min_slippage_bps (int): 最小滑点， 单位是 bps
        max_slippage_bps (int): 最大滑点， 单位是 bps
        swap_mode (str, optional): 交易模式. Defaults to "ExactIn".
        price_impact_multiplier (float, optional): price impact 的倍数. Defaults to 1.5.
        default_slippage_bps (int, optional): 默认滑点. Defaults to 500.
        max_retries (int, optional): 最大重试次数. Defaults to 3.

    Returns:
        int: 滑点（bps）

    Raises:
        ValueError: 参数验证失败时抛出
        Exception: 其他错误时抛出
    """
    if amount <= 0:
        raise ValueError("Amount must be positive")
    if min_slippage_bps >= max_slippage_bps:
        raise ValueError("min_slippage_bps must be less than max_slippage_bps")
    if swap_mode not in ["ExactIn", "ExactOut"]:
        raise ValueError("Invalid swap_mode")

    logger.info(
        f"Calculating slippage for {amount} {input_mint} -> {output_mint}, "
        f"mode: {swap_mode}, min: {min_slippage_bps} bps, max: {max_slippage_bps} bps"
    )

    jupiter = get_jupiter_client()
    try:
        quote = await jupiter.quote(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount,
            swap_mode=swap_mode,
        )  # type: ignore[reportArgumentType]

        # price_impact 是 0~1 的小数
        price_impact = Decimal(quote["priceImpactPct"])
        # 转换为百分比
        price_impact_pct = float(price_impact * 100)

        # 基础滑点为 price impact 的倍数
        slippage = price_impact_pct * price_impact_multiplier
        slippage = max(slippage, min_slippage_bps / 100)
        slippage = min(slippage, max_slippage_bps / 100)

        logger.info(
            f"Slippage calculation: price_impact={price_impact_pct}%, "
            f"multiplier={price_impact_multiplier}, final_slippage={slippage}%"
        )
        return int(slippage * 100)  # 转换为 bps
    except Exception as e:
        logger.warning(f"Unexpected error while calculating slippage: {e}")
        return default_slippage_bps
