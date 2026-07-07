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


@dataclass
class TestResult:
    name: str
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
            raise

    def get(self, path: str, token: str | None = None) -> tuple[int, Any]:
        return self.request("GET", path, token=token)

    def post(
        self,
        path: str,
        body: dict[str, Any],
        token: str | None = None,
        expected_error: int | None = None,
    ) -> tuple[int, Any]:
        return self.request("POST", path, body, token, expected_error)


def assert_result(results: list[TestResult], name: str, condition: bool, detail: str) -> None:
    results.append(TestResult(name=name, passed=condition, detail=detail))
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def run_security_regression(base_url: str) -> list[TestResult]:
    client = ApiClient(base_url)
    results: list[TestResult] = []

    _, health = client.get("/health")
    assert_result(
        results,
        "health check",
        health["status"] == "ok",
        f"/health returned {health}",
    )

    _, alice = client.post(
        "/auth/register",
        {
            "username": "alice",
            "password": "alice123",
            "tenant_id": "tenant-a",
            "role": "user",
        },
    )
    _, bob = client.post(
        "/auth/register",
        {
            "username": "bob",
            "password": "bob12345",
            "tenant_id": "tenant-b",
            "role": "user",
        },
    )
    assert_result(
        results,
        "users registered",
        alice["id"] != bob["id"] and alice["tenant_id"] != bob["tenant_id"],
        f"alice={alice}, bob={bob}",
    )

    _, alice_login = client.post(
        "/auth/login",
        {"username": "alice", "password": "alice123"},
    )
    _, bob_login = client.post(
        "/auth/login",
        {"username": "bob", "password": "bob12345"},
    )
    alice_token = alice_login["access_token"]
    bob_token = bob_login["access_token"]
    assert_result(
        results,
        "tokens issued",
        bool(alice_token) and bool(bob_token) and alice_token != bob_token,
        "Alice and Bob received distinct bearer tokens.",
    )

    _, private_doc = client.post(
        "/documents",
        {
            "title": "Alice private document",
            "content": "This is Alice private document.",
        },
        token=alice_token,
    )
    bob_doc_status, _ = client.request(
        "GET",
        f"/documents/{private_doc['id']}",
        token=bob_token,
        expected_error=403,
    )
    assert_result(
        results,
        "document direct access blocked",
        bob_doc_status == 403,
        "Bob cannot read Alice document through direct document API.",
    )

    _, rag_doc = client.post(
        "/documents",
        {
            "title": "Alice secret plan",
            "content": (
                "Project phoenix secret: Alice owns this private RAG document. "
                "Bob must not retrieve it through the safe RAG endpoint."
            ),
        },
        token=alice_token,
    )
    assert_result(
        results,
        "rag document created",
        rag_doc["owner_id"] == alice["id"],
        f"RAG document owner is {rag_doc['owner_id']}",
    )

    _, alice_safe_rag = client.post(
        "/rag/query",
        {"query": "phoenix secret", "max_results": 5},
        token=alice_token,
    )
    _, bob_safe_rag = client.post(
        "/rag/query",
        {"query": "phoenix secret", "max_results": 5},
        token=bob_token,
    )
    _, bob_vulnerable_rag = client.post(
        "/lab/vulnerable-rag/query",
        {"query": "phoenix secret", "max_results": 5},
        token=bob_token,
    )
    assert_result(
        results,
        "safe RAG allows owner retrieval",
        alice_safe_rag["match_count"] >= 1,
        f"Alice safe RAG match_count={alice_safe_rag['match_count']}",
    )
    assert_result(
        results,
        "safe RAG blocks cross-user retrieval",
        bob_safe_rag["match_count"] == 0,
        f"Bob safe RAG match_count={bob_safe_rag['match_count']}",
    )
    assert_result(
        results,
        "vulnerable RAG demonstrates leakage",
        bob_vulnerable_rag["match_count"] >= 1
        and bob_vulnerable_rag["matches"][0]["owner_id"] == alice["id"],
        f"Bob vulnerable RAG response={bob_vulnerable_rag}",
    )

    _, order = client.post(
        "/orders",
        {
            "item_name": "Security Book",
            "shipping_address": "Alice Old Address",
        },
        token=alice_token,
    )
    assert_result(
        results,
        "order created",
        order["owner_id"] == alice["id"],
        f"Order owner is {order['owner_id']}",
    )

    bob_safe_query_status, _ = client.post(
        "/agent/tools/order-query",
        {"order_id": order["id"]},
        token=bob_token,
        expected_error=403,
    )
    _, bob_vulnerable_query = client.post(
        "/lab/vulnerable-agent/order-query",
        {"order_id": order["id"]},
        token=bob_token,
    )
    bob_safe_update_status, _ = client.post(
        "/agent/tools/address-update",
        {
            "order_id": order["id"],
            "new_address": "Bob Attack Address",
        },
        token=bob_token,
        expected_error=403,
    )
    _, bob_vulnerable_update = client.post(
        "/lab/vulnerable-agent/address-update",
        {
            "order_id": order["id"],
            "new_address": "Bob Attack Address",
        },
        token=bob_token,
    )
    _, alice_orders = client.get("/orders", token=alice_token)

    assert_result(
        results,
        "safe Agent order query blocks cross-user access",
        bob_safe_query_status == 403,
        "Bob cannot query Alice order through safe Agent tool.",
    )
    assert_result(
        results,
        "vulnerable Agent order query demonstrates leakage",
        bob_vulnerable_query["order"]["owner_id"] == alice["id"],
        f"Vulnerable query response={bob_vulnerable_query}",
    )
    assert_result(
        results,
        "safe Agent address update blocks cross-user write",
        bob_safe_update_status == 403,
        "Bob cannot update Alice order through safe Agent tool.",
    )
    assert_result(
        results,
        "vulnerable Agent address update demonstrates write impact",
        bob_vulnerable_update["order"]["shipping_address"] == "Bob Attack Address",
        f"Vulnerable update response={bob_vulnerable_update}",
    )
    assert_result(
        results,
        "owner observes vulnerable write impact",
        alice_orders[0]["shipping_address"] == "Bob Attack Address",
        f"Alice orders={alice_orders}",
    )

    return results


def print_results(results: list[TestResult]) -> None:
    print("\nSecurity regression results")
    print("=" * 28)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.name} - {result.detail}")
    print("=" * 28)
    print(f"Total: {len(results)} passed, 0 failed")


def wait_until_ready(client: ApiClient, timeout_seconds: float = 10) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            _, health = client.get("/health")
            if health["status"] == "ok":
                return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("test server did not become ready")


def run_with_embedded_server(host: str, port: int) -> list[TestResult]:
    server = uvicorn.Server(
        uvicorn.Config(app, host=host, port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        base_url = f"http://{host}:{port}"
        wait_until_ready(ApiClient(base_url))
        return run_security_regression(base_url)
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run AI-RAG-Security-Audit security regression tests."
    )
    parser.add_argument(
        "--base-url",
        help="Run tests against an already running server, for example http://127.0.0.1:8000.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()

    try:
        if args.base_url:
            results = run_security_regression(args.base_url)
        else:
            results = run_with_embedded_server(args.host, args.port)
        print_results(results)
        return 0
    except Exception as error:
        print(f"\n[FAIL] security regression failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
