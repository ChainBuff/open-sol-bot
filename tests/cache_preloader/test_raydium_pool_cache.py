from unittest.mock import AsyncMock, patch

import aioredis
import pytest
from cache_preloader.caches.raydium_pool import RaydiumPoolCache

from libs.cache.solbot_cache.rayidum import MintPoolDataCache


@pytest.fixture
def mock_redis():
    """模拟 Redis 客户端"""
    redis = AsyncMock(spec=aioredis.Redis)
    redis.set = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.zadd = AsyncMock()
    redis.zrange = AsyncMock(return_value=[])
    redis.zrem = AsyncMock()
    redis.exists = AsyncMock(return_value=0)
    return redis


@pytest.fixture
def mock_rpc_client():
    """模拟 RPC 客户端"""
    client = AsyncMock()
    client.get_account_info = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_mint_pool_data_cache(mock_redis):
    """测试 Mint 池数据缓存"""
    cache = MintPoolDataCache(mock_redis)

    # 这里可以添加测试，例如测试设置和获取缓存数据


@pytest.mark.asyncio
async def test_raydium_pool_cache_initialization():
    """测试 Raydium 池缓存初始化"""
    with patch("cache_preloader.caches.raydium_pool.AsyncClient") as mock_client:
        redis = AsyncMock(spec=aioredis.Redis)
        cache = RaydiumPoolCache("https://api.mainnet-beta.solana.com", redis, 5)

        # 验证初始状态
        assert not cache.is_running()
        assert cache.max_concurrent_tasks == 5
        assert cache.redis == redis


# 注意：由于 RaydiumPoolCache 的完整实现较为复杂，
# 这里只提供了基本的测试框架。实际测试应该根据完整实现进行扩展。
