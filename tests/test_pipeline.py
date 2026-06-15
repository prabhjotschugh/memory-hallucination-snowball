"""
Smoke test — verifies the full pipeline structure works correctly.
Does NOT make real LLM calls. Tests memory, injector, tools, runner wiring.

Run:
    python tests/test_pipeline.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline.memory import MemoryStore, MemoryEntry
from pipeline.tools import ToolRegistry, FinancialDataTool, FailureMode, ToolResult
from pipeline.injector import HallucinationInjector


def test_memory_write_and_lineage():
    print("Testing MemoryStore...")
    store = MemoryStore()

    # write root (injected hallucination)
    e0 = store.write(
        key="revenue_q1",
        value="27000",  # wrong
        session_id=1,
        source="injected",
        force_contaminated=True,
        force_generation=0,
    )
    assert e0.is_contaminated
    assert e0.generation == 0

    # write child entry that references e0
    e1 = store.write(
        key="growth_rate_q1_q2",
        value="-12% (based on Q1 revenue 27000)",
        session_id=2,
        parent_ids=[e0.entry_id],
        source="agent",
    )
    assert e1.is_contaminated, "Child of contaminated entry should be contaminated"
    assert e1.generation == 1

    # write grandchild
    e2 = store.write(
        key="projection_q3",
        value="Projected further decline based on trend",
        session_id=3,
        parent_ids=[e1.entry_id],
        source="agent",
    )
    assert e2.is_contaminated
    assert e2.generation == 2

    # clean entry (no contaminated parents)
    e3 = store.write(
        key="employee_count",
        value="95000",
        session_id=1,
        source="agent",
    )
    assert not e3.is_contaminated
    assert e3.generation == 0

    assert store.contamination_cluster_size(after_session=3) == 3
    assert len(store) == 4

    lineage = store.get_lineage_graph()
    assert e1.entry_id in lineage.get(e0.entry_id, [])

    print("  MemoryStore: PASS")


def test_injector():
    print("Testing HallucinationInjector...")
    injector = HallucinationInjector()
    injector.add_injection(
        session_id=1,
        key="revenue_q1",
        corrupted_value="27000",
        true_value="34229",
        severity="high",
    )

    # should inject
    val, injected, spec = injector.check_and_inject(1, "revenue_q1", "34229")
    assert injected
    assert val == "27000"
    assert spec.applied

    # should not inject again (already applied)
    val2, injected2, _ = injector.check_and_inject(1, "revenue_q1", "34229")
    assert not injected2
    assert val2 == "34229"

    # wrong session — should not inject
    injector2 = HallucinationInjector()
    injector2.add_injection(2, "some_key", "bad", "good", "subtle")
    val3, injected3, _ = injector2.check_and_inject(1, "some_key", "good")
    assert not injected3

    summary = injector.summary()
    assert summary["applied"] == 1
    print("  HallucinationInjector: PASS")


def test_tool_failure_modes():
    print("Testing FinancialDataTool failure modes...")

    gt = {"3M_2022_10K_revenue": "34229"}

    # baseline — no failure
    tool = FinancialDataTool(gt, failure_mode=FailureMode.NONE)
    result = tool.query("3M_2022_10K_revenue")
    assert result.success
    assert result.result == "34229"
    assert not result.is_hallucinated

    # wrong value — always fail
    tool_fail = FinancialDataTool(gt, failure_mode=FailureMode.WRONG_VALUE, failure_rate=1.0)
    result_fail = tool_fail.query("3M_2022_10K_revenue")
    assert result_fail.success  # tool appears to succeed
    assert result_fail.is_hallucinated  # but it's wrong
    assert result_fail.result != "34229"

    # missing key
    result_miss = tool.query("nonexistent_key")
    assert not result_miss.success

    print("  FinancialDataTool: PASS")


def test_memory_context_string():
    print("Testing memory context string formatting...")
    store = MemoryStore()
    store.write("revenue_q1", "34229", session_id=1)
    store.write("net_income_q1", "5777", session_id=1)
    store.write("growth_rate", "+4.2%", session_id=2)

    # session 2 should only see session 1 entries
    ctx = store.to_context_string(session_id=2)
    assert "Session 1" in ctx
    assert "revenue_q1" in ctx
    assert "growth_rate" not in ctx  # session 2 shouldn't see session 2

    # session 3 should see sessions 1 and 2
    ctx3 = store.to_context_string(session_id=3)
    assert "growth_rate" in ctx3

    print("  Context string: PASS")


def test_cluster_metrics():
    print("Testing cluster metrics...")
    store = MemoryStore()

    # session 1: inject one hallucination
    e0 = store.write("rev", "27000", 1, force_contaminated=True, force_generation=0)

    # session 2: two children
    e1 = store.write("growth", "-10%", 2, parent_ids=[e0.entry_id])
    e2 = store.write("margin", "22%", 2, parent_ids=[e0.entry_id])

    # session 3: grandchildren
    e3 = store.write("proj", "decline", 3, parent_ids=[e1.entry_id, e2.entry_id])
    e4 = store.write("rec", "SELL", 3, parent_ids=[e3.entry_id])

    assert store.contamination_cluster_size(1) == 1
    assert store.contamination_cluster_size(2) == 3
    assert store.contamination_cluster_size(3) == 5

    by_gen = store.cluster_by_generation(3)
    assert by_gen[0] == 1  # root
    assert by_gen[1] == 2  # children
    assert by_gen[2] == 1  # grandchild (e3)
    assert by_gen[3] == 1  # great-grandchild (e4)

    print("  Cluster metrics: PASS")


if __name__ == "__main__":
    test_memory_write_and_lineage()
    test_injector()
    test_tool_failure_modes()
    test_memory_context_string()
    test_cluster_metrics()
    print("\nAll tests passed.")
