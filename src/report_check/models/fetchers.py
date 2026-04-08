"""示例 token fetcher —— 演示如何注册自定义动态 token 获取逻辑。

实际使用时替换为真实认证接口调用即可。
"""
from report_check.models.token_fetcher import register_token_fetcher


@register_token_fetcher("example")
async def example_fetcher(account: str, password: str, **kwargs) -> str:
    """示例：调用认证接口获取动态 token。

    返回的字符串会直接设置到 Authorization header 中（无 Bearer 前缀）。
    """
    # TODO: 替换为实际认证接口
    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://your-auth-endpoint/api/v1/auth/token",
            json={"account": account, "password": password},
        )
        resp.raise_for_status()
        return resp.json()["token"]
