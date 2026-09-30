# Sample Test Queries for Telecom Agentic AI Operations Center

This guide provides **5 targeted test questions** for each of the four core components:
1. [LlamaIndex Document RAG](#1-llamaindex-document-rag-5-questions)
2. [LlamaIndex Semantic SQL](#2-llamaindex-semantic-sql-5-questions)
3. [Network Diagnostics ADK Agent (Port 8001)](#3-network-diagnostics-agent-port-8001--5-questions)
4. [Billing Resolution ADK Agent (Port 8002)](#4-billing-resolution-agent-port-8002--5-questions)

Each question includes the query string, expected underlying tools/data sources, and expected results.

---

## 1. LlamaIndex Document RAG (5 Questions)

**Component Script:** `llamaindex_rag/document_rag.py`  
**Data Sources:** Policy documents in `data/documents/` (`5g_faq.txt`, `billing_disputes_policy.txt`, `device_upgrade_policy.txt`, `network_outage_procedures.txt`, `roaming_policy.txt`, `sla_policy.txt`).

### Query 1.1: Billing Dispute Window
- **Prompt:**
  > *"What is the dispute window for a customer to contest a charge on their Prodapt bill according to the billing disputes policy?"*
- **Target Document:** `data/documents/billing_disputes_policy.txt` (Section 2)
- **Expected Outcome:** The RAG system explains that customers have a standard dispute window (e.g., 60 days from invoice date) to submit billing disputes, and outlines the required dispute submission criteria.

### Query 1.2: Outage Severity Classification
- **Prompt:**
  > *"What specific criteria define a CRITICAL severity network outage versus a MAJOR outage under NOC procedures?"*
- **Target Document:** `data/documents/network_outage_procedures.txt` (Section 2)
- **Expected Outcome:** Explains that CRITICAL outages typically involve complete site outages, regional core network failures, or events affecting over a defined customer threshold (e.g., > 5,000 customers or critical public safety services), whereas MAJOR outages represent localized degradation or redundant route losses.

### Query 1.3: Early Device Upgrade & Trade-In
- **Prompt:**
  > *"What are the eligibility requirements for an early handset upgrade on a 36-month installment plan, and what trade-in rules apply?"*
- **Target Document:** `data/documents/device_upgrade_policy.txt` (Sections 2 & 4)
- **Expected Outcome:** Details the percentage of installment paid (e.g., 50% / 18 months), requirement that account must not be past due, device condition inspection requirements, and trade-in credit valuation mechanics.

### Query 1.4: International Roaming & Travel Pass
- **Prompt:**
  > *"How does the daily Travel Pass work for international roaming, and what is the spend cap under the roaming policy?"*
- **Target Document:** `data/documents/roaming_policy.txt` (Sections 2 & 3)
- **Expected Outcome:** Identifies the international roaming zone tiers (Zones A through D), the fixed daily Travel Pass charge for high-speed data, pay-per-use fallback rates, and safety spend caps protecting customers against bill shock.

### Query 1.5: SLA Outage Credits & Calculation
- **Prompt:**
  > *"Under the SLA policy, what duration of service outage entitles a customer to an automatic bill credit, and how is the credit amount calculated?"*
- **Target Document:** `data/documents/sla_policy.txt` (Sections 2 & 3)
- **Expected Outcome:** References monthly uptime commitments, qualifying continuous outage thresholds (e.g., outages lasting more than 4 or 6 hours), and the proportional monthly service fee credit calculation table.

---

## 2. LlamaIndex Semantic SQL (5 Questions)

**Component Script:** `llamaindex_rag/sql_semantic_search.py`  
**Database:** `data/telecom_ops.db`  
**Target Tables:** `network_towers`, `network_outages`, `tower_performance`, `customer_subscriptions`.

### Query 2.1: Non-Operational Cell Towers
- **Prompt:**
  > *"Which cell towers are currently not in OPERATIONAL status, and what are their locations and technologies?"*
- **Target SQL:**
  ```sql
  SELECT tower_id, tower_name, region, city, state, technology, status
  FROM network_towers
  WHERE status != 'OPERATIONAL';
  ```
- **Expected Outcome:** Returns towers such as `TX-208` (Dallas - DEGRADED), `IL-221` (Chicago - DEGRADED), and `MA-055` (Boston - MAINTENANCE).

### Query 2.2: Critical Outage Analytics by Region
- **Prompt:**
  > *"What was the total number of customers affected and the total outage duration for all CRITICAL outages in the Southwest region?"*
- **Target SQL:**
  ```sql
  SELECT COUNT(*) AS outage_count,
         SUM(affected_customers) AS total_customers_affected,
         SUM(duration_hours) AS total_duration_hours
  FROM network_outages
  WHERE severity = 'CRITICAL' AND region = 'Southwest';
  ```
- **Expected Outcome:** Summarizes cumulative affected users and total outage hours from historical events in the Southwest region.

### Query 2.3: Towers with Worst Packet Loss
- **Prompt:**
  > *"Which 5 cell towers have recorded the highest packet loss percentage in their latest performance telemetry?"*
- **Target SQL:**
  ```sql
  SELECT t.tower_id, t.tower_name, t.city, p.packet_loss_pct, p.recorded_at
  FROM tower_performance p
  JOIN network_towers t ON p.tower_id = t.tower_id
  WHERE p.recorded_at = (SELECT MAX(recorded_at) FROM tower_performance WHERE tower_id = p.tower_id)
  ORDER BY p.packet_loss_pct DESC
  LIMIT 5;
  ```
- **Expected Outcome:** Lists top 5 degraded sites with highest packet loss percentages along with timestamp.

### Query 2.4: Subscription Distribution by Plan & Type
- **Prompt:**
  > *"How many active customer subscriptions are there for each account type (Consumer, Business, Enterprise)?"*
- **Target SQL:**
  ```sql
  SELECT account_type, COUNT(*) AS active_subscriptions, AVG(monthly_fee) AS avg_fee
  FROM customer_subscriptions
  WHERE status = 'ACTIVE'
  GROUP BY account_type;
  ```
- **Expected Outcome:** Groups active lines into Consumer, Business, and Enterprise tiers with respective line counts and average fees.

### Query 2.5: Historical Outage Root Causes
- **Prompt:**
  > *"What are the most frequent root causes of network outages, and how many times has each occurred?"*
- **Target SQL:**
  ```sql
  SELECT root_cause, COUNT(*) AS occurrence_count, AVG(duration_hours) AS avg_duration
  FROM network_outages
  GROUP BY root_cause
  ORDER BY occurrence_count DESC;
  ```
- **Expected Outcome:** Categorizes root causes (e.g., Fiber cut, Hardware failure, Power loss) sorted by incident frequency.

---

## 3. Network Diagnostics Agent (Port 8001 / ADK) (5 Questions)

**Service URL:** `http://localhost:8001`  
**Agent Card:** `http://localhost:8001/.well-known/agent-card.json`  
**Available Tools:** `check_tower_status`, `run_connectivity_diagnostics`, `get_regional_network_summary`.

### Query 3.1: Check a Degraded Cell Tower
- **Prompt:**
  > *"Check the operational status, current performance metrics, and any active incidents for cell tower TX-208 in Dallas."*
- **Tools Invoked:** `check_tower_status("TX-208")`
- **Expected Outcome:** Reports that tower TX-208 is currently in `DEGRADED` status, provides latency/throughput/packet loss metrics, and references any open incidents in Dallas.

### Query 3.2: Inspect an Operational 5G mmWave Tower
- **Prompt:**
  > *"What is the status and health of Manhattan cell tower NY-301?"*
- **Tools Invoked:** `check_tower_status("NY-301")`
- **Expected Outcome:** Confirms `NY-301` (`Manhattan Midtown`) is `OPERATIONAL` with `5G mmWave`, reporting low latency and healthy throughput.

### Query 3.3: Inspect a Scheduled Maintenance Site
- **Prompt:**
  > *"Inspect cell tower MA-055 in Boston and check why throughput or connectivity might be affected."*
- **Tools Invoked:** `check_tower_status("MA-055")`
- **Expected Outcome:** Identifies that `MA-055` (`Boston Seaport`) is in `MAINTENANCE` status, advising that degraded metrics are expected due to ongoing engineering work.

### Query 3.4: Customer End-to-End Connectivity Diagnostics
- **Prompt:**
  > *"Run connectivity diagnostics for customer CUST-10002 to identify if their connection issues are related to tower performance."*
- **Tools Invoked:** `run_connectivity_diagnostics("CUST-10002")`
- **Expected Outcome:** Looks up customer `CUST-10002`'s primary attached tower, evaluates RF signal strength, packet loss, and latency, and provides a clear recommendation.

### Query 3.5: Regional Network Health Summary
- **Prompt:**
  > *"Provide a complete network health summary for the Southwest region including operational tower ratios and active incidents."*
- **Tools Invoked:** `get_regional_network_summary("Southwest")`
- **Expected Outcome:** Aggregates tower counts across Texas/Southwest, computing percent operational vs. degraded and listing active incidents.

---

## 4. Billing Resolution Agent (Port 8002 / ADK) (5 Questions)

**Service URL:** `http://localhost:8002`  
**Agent Card:** `http://localhost:8002/.well-known/agent-card.json`  
**Available Tools:** `lookup_billing_account`, `check_duplicate_charges`, `apply_billing_credit`.

### Query 4.1: Investigate Duplicate Charges (Customer CUST-10002)
- **Prompt:**
  > *"Customer CUST-10002 was charged twice. Check the account and duplicate charges."*
- **Tools Invoked:** `lookup_billing_account("CUST-10002")`, `check_duplicate_charges("CUST-10002")`
- **Expected Outcome:**
  - Retrieves customer **Alex Romero** (Current Balance: $111.98 / $91.98).
  - Identifies duplicate charge `CHG-50022` ("Unlimited Plus" for $65.99 on 2026-09-01).
  - Explains the duplicate charge is on the open bill.

### Query 4.2: Account Balance & Recent Invoice Lookup
- **Prompt:**
  > *"Look up customer CUST-10008, and provide their account status, current balance, and recent invoice charges."*
- **Tools Invoked:** `lookup_billing_account("CUST-10008")`
- **Expected Outcome:** Returns account details for **Maya Chen**, current balance ($137.99), currency (USD), account status (ACTIVE), and the 5 most recent charges.

### Query 4.3: Duplicate Charge Audit (Customer CUST-10027)
- **Prompt:**
  > *"Check whether customer CUST-10027 has any duplicate charges flagged on their account."*
- **Tools Invoked:** `check_duplicate_charges("CUST-10027")`
- **Expected Outcome:** Returns `duplicate_count: 1` with details of duplicate charge ($12.00 add-on fee) flagged with `is_duplicate_flag = 1`.

### Query 4.4: Auto-Approved Credit Test (≤ $50.00 Limit)
- **Prompt:**
  > *"Customer CUST-10040 experienced a brief network disruption. Apply a courtesy credit of $10.00 with reason 'Network outage courtesy credit'."*
- **Tools Invoked:** `apply_billing_credit("CUST-10040", 10.0, "Network outage courtesy credit")`
- **Expected Outcome:**
  - Status: `APPLIED` (since $10.00 ≤ $50.00 auto-approval threshold).
  - Customer balance is immediately reduced by $10.00.
  - Returns updated balance and success message.

### Query 4.5: Supervisor Approval Credit Test (> $50.00 Limit)
- **Prompt:**
  > *"Customer CUST-10011 is disputing an incorrect roaming charge. Apply a billing credit of $80.00 with reason 'Disputed international roaming charge'."*
- **Tools Invoked:** `apply_billing_credit("CUST-10011", 80.0, "Disputed international roaming charge")`
- **Expected Outcome:**
  - Status: `PENDING_APPROVAL` (since $80.00 > $50.00 auto-approval threshold).
  - Invariant verified: Customer balance is **not** modified immediately.
  - Explains clearly that credit has been recorded and submitted for supervisor authorization.

---

## 5. Quick Test Python Script

Save and run this snippet to test both live A2A services in seconds:

```python
import asyncio
from google.genai.types import Content, Part
from google.adk.runners import InMemoryRunner
from google.adk.a2a.agent import RemoteA2aAgent

async def test_a2a_agent(name: str, card_url: str, prompt: str):
    print(f"\n{'='*70}\nQuerying: {name}\nCard: {card_url}\nPrompt: {prompt}\n{'='*70}")
    remote_agent = RemoteA2aAgent(name=name, agent_card=card_url)
    runner = InMemoryRunner(agent=remote_agent)
    session = await runner.session_service.create_session(app_name=name, user_id="tester")
    msg = Content(role="user", parts=[Part.from_text(text=prompt)])

    async for event in runner.run_async(session_id=session.id, user_id="tester", new_message=msg):
        if event.content and event.content.parts:
            for p in event.content.parts:
                if p.text:
                    print(p.text)

async def main():
    # 1. Test Network Diagnostics (Port 8001)
    await test_a2a_agent(
        name="net_diag",
        card_url="http://localhost:8001/.well-known/agent-card.json",
        prompt="Check the operational status and recent performance metrics for cell tower TX-208 in Dallas."
    )

    # 2. Test Billing Resolution (Port 8002)
    await test_a2a_agent(
        name="billing_res",
        card_url="http://localhost:8002/.well-known/agent-card.json",
        prompt="Customer CUST-10002 was charged twice. Check the account and duplicate charges."
    )

if __name__ == "__main__":
    asyncio.run(main())
```
