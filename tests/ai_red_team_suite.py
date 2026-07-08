import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app  # noqa: E402


CASES_PATH = Path(__file__).with_name("ai_security_cases.json")


@dataclass
class RedTeamResult:
    case_id: str
    category: str
    passed: bool
    detail: str


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        token: str | None = None,
        expected_error: int | None = None,
    ) -> tuple[int, Any]:
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers=headers,
        )

        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = response.read().decode("utf-8")
                return response.status, json.loads(payload) if payload else None
        except urllib.error.HTTPError as error:
            if expected_error is not None and error.code == expected_error:
                return error.code, None
            payload = error.read().decode("utf-8")
            raise AssertionError(f"HTTP {error.code}: {payload}") from error

    def get(
        self,
        path: str,
        token: str | None = None,
        expected_error: int | None = None,
    ) -> tuple[int, Any]:
        return self.request("GET", path, token=token, expected_error=expected_error)

    def post(
        self,
        path: str,
        body: dict[str, Any],
        token: str | None = None,
        expected_error: int | None = None,
    ) -> tuple[int, Any]:
        return self.request("POST", path, body, token, expected_error)


def load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        cases = json.load(file)
    if not isinstance(cases, list):
        raise ValueError("AI security cases file must contain a list.")
    return cases


def resolve_value(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        resolved = value
        for key, replacement in context.items():
            resolved = resolved.replace(f"{{{{{key}}}}}", str(replacement))
        return resolved
    if isinstance(value, dict):
        return {key: resolve_value(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_value(item, context) for item in value]
    return value


def get_actor_token(case: dict[str, Any], context: dict[str, Any]) -> str:
    attacker = case["attacker"]
    return context[f"{attacker}_token"]


def run_case(
    client: ApiClient,
    case: dict[str, Any],
    context: dict[str, Any],
) -> RedTeamResult:
    case_id = case["id"]
    endpoint = resolve_value(case["endpoint"], context)
    payload = resolve_value(case["payload"], context)
    token = get_actor_token(case, context)

    try:
        if case_id == "direct_document_idor_blocked":
            status, _ = client.get(endpoint, token=token, expected_error=403)
            assert status == 403
            detail = "Bob was blocked from directly reading Alice's document."

        elif case_id == "safe_rag_prompt_injection_blocked":
            _, response = client.post(endpoint, payload, token=token)
            assert response["match_count"] == 0, response
            detail = "Safe RAG returned zero cross-user matches."

        elif case_id == "vulnerable_rag_prompt_injection_leaks":
            _, response = client.post(endpoint, payload, token=token)
            assert response["match_count"] >= 1, response
            assert response["matches"][0]["owner_id"] == context["alice_user_id"], response
            detail = "Vulnerable RAG leaked Alice's private chunk to Bob."

        elif case_id == "safe_agent_order_query_idor_blocked":
            status, _ = client.post(endpoint, payload, token=token, expected_error=403)
            assert status == 403
            detail = "Safe Agent read tool blocked Bob's cross-user order query."

        elif case_id == "vulnerable_agent_order_query_idor_leaks":
            _, response = client.post(endpoint, payload, token=token)
            assert response["order"]["owner_id"] == context["alice_user_id"], response
            detail = "Vulnerable Agent read tool returned Alice's order to Bob."

        elif case_id == "safe_agent_address_update_idor_blocked":
            status, _ = client.post(endpoint, payload, token=token, expected_error=403)
            assert status == 403
            detail = "Safe Agent write tool blocked Bob before any confirmation step."

        elif case_id == "vulnerable_agent_address_update_idor_writes":
            _, response = client.post(endpoint, payload, token=token)
            assert response["order"]["shipping_address"] == payload["new_address"], response
            detail = "Vulnerable Agent write tool changed Alice's order address."

        elif case_id == "safe_address_update_requires_confirmation":
            _, response = client.post(endpoint, payload, token=token)
            assert response["requires_confirmation"] is True, response
            assert response["confirmation_token"], response
            context["alice_confirmation_token"] = response["confirmation_token"]
            detail = "Safe write returned a confirmation token instead of updating immediately."

        elif case_id == "safe_confirmation_token_accepts_exact_request":
            _, response = client.post(endpoint, payload, token=token)
            assert response["requires_confirmation"] is False, response
            assert response["order"]["shipping_address"] == payload["new_address"], response
            detail = "Exact confirmed write succeeded for Alice."

        elif case_id == "safe_confirmation_token_reuse_blocked":
            status, _ = client.post(endpoint, payload, token=token, expected_error=403)
            assert status == 403
            detail = "Consumed confirmation token could not be reused."

        elif case_id == "safe_confirmation_token_mismatch_blocked":
            confirmation_payload = {
                "order_id": context["alice_order_id"],
                "new_address": "Alice Token Original Address",
            }
            _, confirmation = client.post(
                "/agent/tools/address-update",
                confirmation_payload,
                token=token,
            )
            mismatch_payload = dict(payload)
            mismatch_payload["confirmation_token"] = confirmation["confirmation_token"]
            status, _ = client.post(
                endpoint,
                mismatch_payload,
                token=token,
                expected_error=403,
            )
            assert status == 403
            detail = "Confirmation token was rejected after the address was changed."

        elif case_id == "agent_audit_logs_include_denied_and_vulnerable":
            _, response = client.get(endpoint, token=token)
            outcomes = {audit_log["outcome"] for audit_log in response}
            tool_names = {audit_log["tool_name"] for audit_log in response}
            assert {"denied", "vulnerable_success"} <= outcomes, response
            assert {
                "address-update",
                "vulnerable-address-update",
                "vulnerable-order-query",
            } <= tool_names, response
            detail = "Audit logs include denied safe calls and vulnerable demo calls."

        else:
            raise ValueError(f"Unknown case id: {case_id}")

        return RedTeamResult(case_id, case["category"], True, detail)

    except Exception as error:
        return RedTeamResult(case_id, case["category"], False, str(error))


def prepare_scenario(client: ApiClient) -> dict[str, Any]:
    run_id = str(int(time.time() * 1000))
    alice_username = f"red_alice_{run_id}"
    bob_username = f"red_bob_{run_id}"

    _, health = client.get("/health")
    if health["status"] != "ok":
        raise RuntimeError(f"health check failed: {health}")

    _, alice = client.post(
        "/auth/register",
        {
            "username": alice_username,
            "password": "alice123",
            "tenant_id": "tenant-a",
            "role": "user",
        },
    )
    _, bob = client.post(
        "/auth/register",
        {
            "username": bob_username,
            "password": "bob12345",
            "tenant_id": "tenant-b",
            "role": "user",
        },
    )

    _, alice_login = client.post(
        "/auth/login",
        {"username": alice_username, "password": "alice123"},
    )
    _, bob_login = client.post(
        "/auth/login",
        {"username": bob_username, "password": "bob12345"},
    )

    alice_token = alice_login["access_token"]
    bob_token = bob_login["access_token"]

    _, private_document = client.post(
        "/documents",
        {
            "title": "Alice direct-access private note",
            "content": "Alice owns this direct-access private document.",
        },
        token=alice_token,
    )
    _, rag_document = client.post(
        "/documents",
        {
            "title": "Alice phoenix red team note",
            "content": (
                "Project phoenix secret: Alice owns this private RAG document. "
                "Prompt injection must not bypass retrieval authorization."
            ),
        },
        token=alice_token,
    )
    _, order = client.post(
        "/orders",
        {
            "item_name": "Security Book",
            "shipping_address": "Alice Original Address",
        },
        token=alice_token,
    )

    return {
        "alice_user_id": alice["id"],
        "bob_user_id": bob["id"],
        "alice_token": alice_token,
        "bob_token": bob_token,
        "alice_private_document_id": private_document["id"],
        "alice_rag_document_id": rag_document["id"],
        "alice_order_id": order["id"],
    }


def print_results(results: list[RedTeamResult]) -> None:
    print("\nAI security red-team suite")
    print("=" * 31)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.category} / {result.case_id} - {result.detail}")
    passed_count = sum(result.passed for result in results)
    failed_count = len(results) - passed_count
    print("=" * 31)
    print(f"Total: {passed_count} passed, {failed_count} failed")


def wait_until_ready(client: ApiClient, timeout_seconds: float = 10) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            _, health = client.get("/health")
            if health["status"] == "ok":
                return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("red-team test server did not become ready")


def run_red_team_suite(base_url: str, cases_path: Path = CASES_PATH) -> list[RedTeamResult]:
    client = ApiClient(base_url)
    cases = load_cases(cases_path)
    context = prepare_scenario(client)
    return [run_case(client, case, context) for case in cases]


def run_with_embedded_server(host: str, port: int) -> list[RedTeamResult]:
    server = uvicorn.Server(
        uvicorn.Config(app, host=host, port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        base_url = f"http://{host}:{port}"
        wait_until_ready(ApiClient(base_url))
        return run_red_team_suite(base_url)
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run AI security red-team cases against the audit lab."
    )
    parser.add_argument(
        "--base-url",
        help="Run cases against an already running server, for example http://127.0.0.1:8000.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8771)
    args = parser.parse_args()

    try:
        if args.base_url:
            results = run_red_team_suite(args.base_url)
        else:
            results = run_with_embedded_server(args.host, args.port)
        print_results(results)
        return 0 if all(result.passed for result in results) else 1
    except Exception as error:
        print(f"\n[FAIL] AI security red-team suite failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
