# MemorySnowball: The Hallucination Snowball Effect in AI Memory 🧠❄️

This project explores a critical flaw in modern AI agents that use long-term memory. We are proving the **"Hallucination Snowball"** effect: if an AI hallucinates a single fact and saves it to its database, that error doesn't just stay put. As future AI sessions read that memory, the error multiplies, infects new calculations, and corrupts perfectly clean data until it reaches a "Point of No Return."

This repository is the codebase for our A* research paper submission (ICLR 2026 target).

---

## 🛠️ What We Have Built So Far

We are building this project in carefully tested phases to ensure the math and tracking are completely bulletproof.

### Phase 1: The Memory Database (Fixing V1's Bug)
In the first version of this project, there was a bug where the database would automatically assume a child fact was wrong just because its parent was wrong. 
* **What we did:** We built a custom `MemoryStore` and `MemoryEntry` structure using Pydantic. We strictly separated `is_contaminated` (whether the fact is actually mathematically wrong) from `parent_ids` (where the fact came from). 
* **Result:** The system can perfectly trace the lineage of an idea without automatically assuming it's broken.

### Phase 2: The Grader (Tier A Contamination Checker)
We need a way to mathematically prove if the AI is hallucinating, without relying on another AI to grade it.
* **What we did:** We built a strict Python math checker. It uses Regex to rip numbers out of the AI's messy text (converting `"$71.2B"` into `71200000000.0`). It then checks this against the absolute Ground Truth answer key. If it's off by more than 2%, it flags the text as a hallucination.
* **Result:** We have a flawless, automated "Grader" to police the AI agents.

### Phase 3: The First AI Agent (Proving the Engine)
Before building a massive pipeline, we needed to prove our code could talk to an LLM and our Grader could check the output.
* **What we did:** We created the `Researcher` agent using the **Google Gemini 2.5 Flash** model. We gave it a text, asked it a question, and fed its answer into our Grader. We then forcefully injected a fake answer to ensure the Grader caught it.
* **Result:** The connection to Gemini works, and the Grader successfully catches injected errors.

### Phase 4: The 5-Agent Assembly Line
We built the full pipeline for a single session (like a game of telephone).
* **What we did:** We added the `Analyst`, `Writer`, `Reviewer`, and `MemoryCurator`. The Researcher extracts a number -> the Analyst calculates growth -> the Writer writes a sentence -> the Curator grades them all and saves them to the database.
* **Result:** We proved that if we force the Researcher to hallucinate, the Analyst will use that bad number to do bad math, and the Writer will write a bad report. The Curator successfully caught the entire "snowball" and flagged it in the database.

### Phase 5: Time Travel (Cross-Session Memory)
We finally introduced the core mechanic of the paper: reading memories from the past.
* **What we did:** We ran two sessions. In Session 1, we injected a hallucination ($50B instead of $85B). In Session 2, we fed the Researcher a *perfectly clean* document ($100B).
* **Result:** Even though the Session 2 document was clean, the Analyst reached into the database, grabbed the hallucination from Session 1, and calculated wildly incorrect growth (100%). We proved that hallucinations from the past can reach forward in time and corrupt a clean session.

### Phase 6: The Giant Snowball (10-Session Loop)
We proved the core thesis of the paper by measuring the growth of the error over time.
* **What we did:** We looped the pipeline 10 times. We injected one error in Session 1, and let the AI run naturally through Session 10. We tracked the **Cluster Growth** (how many database entries the error infected).
* **Result:** The cluster grew from 2 infected entries in Session 1 to **20 infected entries** by Session 10. The `memory_db.json` showed the Analyst looking at **28 different parent memories** just to make one calculation. We successfully proved the existence of the "Point of No Return," where the bad memories completely overwhelm the clean data.

---

## 🚀 Next Steps

We are currently moving into **Phase 7**. Now that we have proven the Snowball effect exists and will ruin the database, we are going to introduce the "Cure"—our custom **Provenance-Gated Memory Architecture**. 

We will test if explicitly warning the AI about flagged memories can stop the snowball from growing!