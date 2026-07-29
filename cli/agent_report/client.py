import os
from typing import Any

import httpx

DEFAULT_URL = "http://127.0.0.1:8765"
DEFAULT_TIMEOUT = 15.0


class AgentDeckError(Exception):
    """API returned an error response."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class AgentDeckConnectionError(Exception):
    """Could not reach the Agent Deck backend."""


class HubClient:
    def __init__(self, base_url: str | None = None, token: str | None = None,
                 timeout: float = DEFAULT_TIMEOUT):
        self.base_url = (base_url or os.environ.get("AGENT_DECK_URL") or DEFAULT_URL).rstrip("/")
        self.token = token if token is not None else os.environ.get("AGENT_DECK_WRITE_TOKEN", "")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def request(self, method: str, path: str, json_body: dict[str, Any] | None = None,
                params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            response = httpx.request(
                method, url, json=json_body, params=params,
                headers=self._headers(), timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise AgentDeckConnectionError(
                f"Could not reach Agent Deck at {self.base_url} ({exc.__class__.__name__}). "
                "Is the backend running? Start it with scripts\\start-backend.ps1"
            ) from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise AgentDeckError(response.status_code, str(detail))
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, json_body: dict[str, Any] | None = None) -> Any:
        return self.request("POST", path, json_body=json_body)
