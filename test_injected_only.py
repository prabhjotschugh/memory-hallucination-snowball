"""Quick test - only run the injected experiment for 3M"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from tiers.tier1_finance import load_multi_session, run_experiment

multi_session = load_multi_session()
company = "3M"
sessions = multi_session[company]

print("Running INJECTED experiment only...")
run_experiment(company, sessions, "injected")

print("\n\n=== CHECKING RESULTS ===")
import json
with open("results/tier1_3m_injected_metrics.json") as f:
    metrics = json.load(f)

print(f"Injector applied: {metrics['injector']['applied']} / {metrics['injector']['planned']}")
print(f"Injector log:")
for log in metrics['injector']['log']:
    print(f"  {log}")

print(f"\n Detection rates by session:")
for item in metrics['detectability_decay']:
    print(f"  Session {item['session']}: {item['detection_rate']:.1%}")

print(f"\n Cluster growth by session:")
for item in metrics['cluster_growth']:
    print(f"  Session {item['session']}: cluster_size={item['cluster_size']}")
