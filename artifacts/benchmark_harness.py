import time
import json
import statistics
import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from integrations.pii_firewall_adapter import pii_firewall
from src.rag.hybrid_retriever import policy_retriever
from src.agents.graph import compute_payload_hash, agent_graph, execute_action_node, synthesize_node
from src.models import AccessTier, ProposedAction
from src.storage.database import db


def calc_percentiles(times_ms: list) -> dict:
    times_ms.sort()
    n = len(times_ms)
    p50 = times_ms[int(n * 0.50)]
    p95 = times_ms[min(int(n * 0.95), n - 1)]
    p99 = times_ms[min(int(n * 0.99), n - 1)]
    return {
        "iterations": n,
        "mean_ms": round(statistics.mean(times_ms), 3),
        "median_p50_ms": round(p50, 3),
        "p95_ms": round(p95, 3),
        "p99_ms": round(p99, 3),
        "min_ms": round(min(times_ms), 3),
        "max_ms": round(max(times_ms), 3)
    }


async def run_benchmarks():
    print("Initializing components for empirical benchmarking...")
    await db.init_db()
    await policy_retriever.initialize()

    # 1. Benchmark PII Firewall Sanitization
    print("Benchmarking PII Firewall Sanitization (200 iterations)...")
    pii_sample = (
        "Requester Alice Chen needs to expedite workstation purchase with card 4532015000000007, "
        "SSN 123-45-6789, and API key sk_test_51Abcd1234567890abcdef1234."
    )
    pii_times = []
    for _ in range(200):
        t0 = time.perf_counter()
        sanitized, findings = pii_firewall.sanitize_text(pii_sample)
        t1 = time.perf_counter()
        pii_times.append((t1 - t0) * 1000.0)

    # 2. Benchmark Hybrid RAG Retrieval
    print("Benchmarking Hybrid BM25 + Vector Policy Retrieval (100 iterations)...")
    rag_query = "What are the manager approval spending thresholds for ergonomic workstations and IT hardware?"
    rag_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        citations = policy_retriever.retrieve(
            query=rag_query,
            user_access_tier=AccessTier.INTERNAL,
            top_k=3
        )
        t1 = time.perf_counter()
        rag_times.append((t1 - t0) * 1000.0)

    # 3. Benchmark Cryptographic Payload Hashing
    print("Benchmarking Canonical SHA-256 Payload Hash Computation (1,000 iterations)...")
    sample_payload = {
        "action_type": "SAP_CREATE_PURCHASE_ORDER",
        "vendor_id": "SAP-VEN-99104",
        "sku": "WS-ERGO-01",
        "quantity": 5,
        "unit_price": "250.00",
        "total_amount": "1250.00",
        "currency": "USD",
        "cost_center": "8820"
    }
    hash_times = []
    for _ in range(1000):
        t0 = time.perf_counter()
        h = compute_payload_hash(sample_payload)
        t1 = time.perf_counter()
        hash_times.append((t1 - t0) * 1000.0)

    # 4. Benchmark Multi-Agent Requisition Turn Execution
    print("Benchmarking Full Multi-Agent Requisition Workflow Turn (30 iterations)...")
    agent_turn_times = []
    for i in range(30):
        conv_id = f"bench-conv-{i}"
        state = {
            "run_id": f"bench-run-{i}",
            "conversation_id": conv_id,
            "correlation_id": f"bench-corr-{i}",
            "user_id": "usr-alice-01",
            "user_name": "Alice Chen",
            "user_email": "alice.requester@company.internal",
            "user_role": "REQUESTER",
            "user_dept": "IT Systems Engineering",
            "user_tier": "INTERNAL",
            "spending_limit_usd": 0.00,
            "input_text": "Requisition 4 ergonomic workstations for IT engineering team.",
            "events": []
        }
        t0 = time.perf_counter()
        final_state = await agent_graph.ainvoke(state, config={"configurable": {"thread_id": conv_id}})
        t1 = time.perf_counter()
        agent_turn_times.append((t1 - t0) * 1000.0)

    results = {
        "benchmark_metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": "macOS / Apple Silicon",
            "python_version": "3.14.6",
            "runtime_mode": "LOCAL_DETERMINISTIC_ENGINE",
            "note": "All percentiles empirically measured from real script execution on local system."
        },
        "benchmarks": {
            "pii_firewall_sanitization": calc_percentiles(pii_times),
            "hybrid_policy_rag_retrieval": calc_percentiles(rag_times),
            "canonical_sha256_payload_hash": calc_percentiles(hash_times),
            "multi_agent_workflow_turn": calc_percentiles(agent_turn_times)
        }
    }

    with open("artifacts/benchmark-results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\nEmpirical Benchmark Results Summary:")
    print(f"- PII Firewall Sanitization: P50 = {results['benchmarks']['pii_firewall_sanitization']['median_p50_ms']} ms | P95 = {results['benchmarks']['pii_firewall_sanitization']['p95_ms']} ms")
    print(f"- Hybrid RAG Retrieval: P50 = {results['benchmarks']['hybrid_policy_rag_retrieval']['median_p50_ms']} ms | P95 = {results['benchmarks']['hybrid_policy_rag_retrieval']['p95_ms']} ms")
    print(f"- Canonical Payload Hashing: P50 = {results['benchmarks']['canonical_sha256_payload_hash']['median_p50_ms']} ms | P95 = {results['benchmarks']['canonical_sha256_payload_hash']['p95_ms']} ms")
    print(f"- Multi-Agent Turn Latency: P50 = {results['benchmarks']['multi_agent_workflow_turn']['median_p50_ms']} ms | P95 = {results['benchmarks']['multi_agent_workflow_turn']['p95_ms']} ms")
    print("\nSaved to artifacts/benchmark-results.json")


if __name__ == "__main__":
    asyncio.run(run_benchmarks())
