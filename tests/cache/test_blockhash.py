import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
#from solbot_cache.blockhash import BlockhashCache
from cache_preloader.caches.blockhash import BlockhashCache
from solders.hash import Hash


@pytest.fixture
def mock_client():
    client = AsyncMock()
    # 创建一个模拟的 blockhash 响应
    mock_response = MagicMock()
    mock_response.value.blockhash = Hash.default()  # 使用默认的 Hash 对象
    mock_response.value.last_valid_block_height = 100
    client.get_latest_blockhash.return_value = mock_response
    return client


@pytest_asyncio.fixture
async def cache_instance(mock_client):
    """提供一个已初始化的缓存实例"""
    with patch("trading.cache.blockhash.get_async_client", return_value=mock_client):
        cache = BlockhashCache()
        await cache.start()
        try:
            yield cache
        finally:
            await cache.stop()


@pytest.mark.asyncio
async def test_initial_blockhash(cache_instance, mock_client):
    """测试初始化时是否正确获取 blockhash"""
    blockhash, last_valid = await cache_instance.get_blockhash()
    assert isinstance(blockhash, Hash)
    assert isinstance(last_valid, int)
    assert last_valid == 100
    mock_client.get_latest_blockhash.assert_called_once()


@pytest.mark.asyncio
async def test_cache_reuse(cache_instance, mock_client):
    """测试缓存重用机制"""
    # 第一次调用
    await cache_instance.get_blockhash()
    call_count = mock_client.get_latest_blockhash.call_count

    # 短时间内再次调用，应该使用缓存
    await cache_instance.get_blockhash()
    assert mock_client.get_latest_blockhash.call_count == call_count


@pytest.mark.asyncio
async def test_cache_expiry(cache_instance, mock_client):
    """测试缓存过期机制"""
    # 第一次调用
    await cache_instance.get_blockhash()
    initial_calls = mock_client.get_latest_blockhash.call_count

    # 模拟时间流逝，超过有效期
    with patch("time.time", return_value=time.time() + BlockhashCache.VALIDITY_DURATION + 1):
        await cache_instance.get_blockhash()
        assert mock_client.get_latest_blockhash.call_count > initial_calls


@pytest.mark.asyncio
async def test_auto_update(cache_instance, mock_client):
    """测试自动更新机制"""
    # 等待一个更新周期
    await asyncio.sleep(BlockhashCache.UPDATE_INTERVAL + 1)
    assert mock_client.get_latest_blockhash.call_count > 1


@pytest.mark.asyncio
async def test_error_handling(mock_client):
    """测试错误处理"""
    mock_client.get_latest_blockhash.side_effect = Exception("API Error")

    with patch("trading.cache.blockhash.get_async_client", return_value=mock_client):
        cache = BlockhashCache()
        with pytest.raises(Exception):
            await cache.start()


@pytest.mark.asyncio
async def test_concurrent_access(cache_instance):
    """测试并发访问"""

    async def access_cache():
        return await cache_instance.get_blockhash()

    # 创建多个并发任务
    tasks = [access_cache() for _ in range(5)]
    results = await asyncio.gather(*tasks)

    # 验证所有结果是否一致
    first_result = results[0]
    for result in results[1:]:
        assert result == first_result
