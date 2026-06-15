import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from pipeline.agents import DataIntakeAgent
from pipeline.memory import MemoryStore
from pipeline.tools import ToolRegistry, FinancialDataTool
from pipeline.injector import HallucinationInjector
from tiers.tier1_finance import build_filing_text_from_evidence, make_key

with open("data/financebench/multi_session.json", "r") as f:
    session_3m = json.load(f)["3M"][0]

filing_text = build_filing_text_from_evidence(session_3m)
print("Filing text length:", len(filing_text))
print("\n=== FILING TEXT (last 2000 chars) ===")
print(filing_text[-2000:])
print("=== END ===\n")

injector = HallucinationInjector()
for q in session_3m["questions"]:
    answer = q["answer"]
    try:
        val_str = answer.replace("$", "").replace(",", "").replace("%", "").strip()
        numeric = float(val_str.split()[0])
        corrupted = str(round(numeric * 0.75, 2))
        key_hint = make_key(q["question"])
        injector.add_injection(
            session_id=1,
            key=key_hint,
            corrupted_value=corrupted,
            true_value=val_str.split()[0],
            severity="high",
        )
        print(f"Injection planned: {key_hint} | true={val_str.split()[0]} | corrupted={corrupted}")
        break
    except Exception as e:
        pass

agent = DataIntakeAgent()
memory = MemoryStore()
tools = ToolRegistry()
# fake financial tool
tools.register("financial_data", FinancialDataTool(ground_truth={}, failure_mode="none"))

print("Running agent...")
out = agent.run(1, filing_text, "3M", session_3m["doc_name"], memory, tools, injector)

print("---")
print("Memory entries:")
for e in memory.entries:
    print(f"  {e.key}: {e.value} | contaminated={e.is_contaminated} | generation={e.generation}")

print("---")
print("Agent memory writes:")
for w in out.memory_writes:
    print(w)

print("---")
print("Injector log:")
print(injector.summary())
