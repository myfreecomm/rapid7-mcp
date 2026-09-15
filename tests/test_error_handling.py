"""Tests for the upstream HTTP error passthrough handler."""

import httpx
import pytest
from fastapi.testclient import TestClient

from rapid7_mcp.client import get_idr_client
from rapid7_mcp.main import app


class _UnauthorizedIDRClient:
    async def get(self, path: str, params: dict | None = None) -> dict:
        request = httpx.Request("GET", f"https://eu.api.insight.rapid7.com{path}")
        response = httpx.Response(401, json={"message": "Unauthorized"}, request=request)
        raise httpx.HTTPStatusError("Unauthorized", request=request, response=response)

    async def post(self, path: str, body: dict | None = None) -> dict:
        raise NotImplementedError


@pytest.fixture
def unauthorized_client() -> TestClient:
    app.dependency_overrides[get_idr_client] = lambda: _UnauthorizedIDRClient()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_upstream_401_is_not_masked_as_500(unauthorized_client: TestClient) -> None:
    response = unauthorized_client.get("/idr/investigations")
    assert response.status_code == 401
    assert response.json() == {"detail": {"message": "Unauthorized"}}
