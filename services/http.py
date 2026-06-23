import typing
import httpx

class HTTPClient:
    """Async HTTP client wrapper using httpx."""

    @staticmethod
    async def request(
        method: typing.Literal["GET", "POST", "PUT", "DELETE", "PATCH"],
        url: str,
        headers: dict | None = None,
        params: dict | None = None,
        json: dict | None = None,
        get: typing.Literal["bytes", "json", "text"] = "json"
    ) -> bytes | dict | str:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json
            )
            response.raise_for_status()

            if get == "bytes":
                return response.content
            elif get == "text":
                return response.text
            else:
                return response.json()

    @staticmethod
    async def get(url: str, headers: dict | None = None, get: typing.Literal["bytes", "json", "text"] = "bytes") -> bytes | dict | str:
        return await HTTPClient.request(method="GET", url=url, headers=headers, get=get)

    @staticmethod
    async def post(url: str, json: dict | None = None, headers: dict | None = None) -> dict:
        return await HTTPClient.request(method="POST", url=url, json=json, headers=headers)