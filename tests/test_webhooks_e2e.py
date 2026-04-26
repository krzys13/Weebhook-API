import asyncio

import httpx
import pytest

BASE_URL = "http://localhost:8000"
HTTPBIN_URL = "http://httpbin:8080"
MAX_RETRIES = 3

@pytest.mark.asyncio
async def test_webhook_happy_path():
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{BASE_URL}/webhooks",
            json={
                "url": f"{HTTPBIN_URL}/post",
                "payload": {"hello": "world"},
            },
        )

        assert response.status_code == 201

        webhook_id = response.json()["id"]

        await asyncio.sleep(3)

        history = await client.get(f"{BASE_URL}/webhooks/{webhook_id}/history")
        assert history.status_code == 200

        operations = history.json()
        assert any(op["status"] == "success" for op in operations)
        assert any(op["status_code"] == 200 for op in operations)


@pytest.mark.asyncio
async def test_webhook_retries_on_500():
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{BASE_URL}/webhooks",
            json={
                "url": f"{HTTPBIN_URL}/status/500",
                "payload": {"should_fail": True},
            },
        )

        assert response.status_code == 201

        webhook_id = response.json()["id"]

        await asyncio.sleep(8)

        history = await client.get(f"{BASE_URL}/webhooks/{webhook_id}/history")
        assert history.status_code == 200

        operations = history.json()
        print(operations)
        failed = [op for op in operations if op["status"] == "failed"]

        assert len(failed) == MAX_RETRIES
        assert any(op["status_code"] == 500 for op in failed)




@pytest.mark.asyncio
async def test_ignore_duplicate_webhooks_within_10_seconds():
    async with httpx.AsyncClient(timeout=10) as client:
        data = {
            "url": f"{HTTPBIN_URL}/post",
            "payload": {"hello": "world"},
        }

        # pierwszy webhook
        response1 = await client.post(f"{BASE_URL}/webhooks", json=data)
        assert response1.status_code == 201

        asyncio.sleep(1)
        # drugi identyczny webhook 
        response2 = await client.post(f"{BASE_URL}/webhooks", json=data)

        
        assert response2.status_code in (200, 202, 409)

        webhook_id_1 = response1.json()["id"]

        # czas na wykonanie przez worker
        await asyncio.sleep(3)

        history = await client.get(f"{BASE_URL}/webhooks/{webhook_id_1}/history")
        assert history.status_code == 200

        operations = history.json()

        # powinno być tylko jedno wykonanie
        successes = [op for op in operations if op["status"] == "success"]
        assert len(successes) == 1


@pytest.mark.asyncio
async def test_invalid_url_returns_422():
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{BASE_URL}/webhooks",
            json={
                "url": "not-a-url",
                "payload": {"x": 1},
            },
        )

        assert response.status_code == 422