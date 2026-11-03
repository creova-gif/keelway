# Keelway business model and agent platform

Companion to `2026-11-01-design-direction-and-roadmap.md`. Written 2026-11-01.
**Recommendation, not decision.** Anything the owner has not confirmed is labelled "hypothesis" or "open".
Market facts come from web search (secondary sources) and need checking against vendor pages before use.

## 1. The thesis in one line

Keelway is the **control layer for AI agents**: any agent runs under your policy, every action is approved,
recorded and verifiable, and your code never has to leave your machine.

Why this and not "a better agent":

- Agents and IDEs are owned by well-funded players (Cognition/Devin Desktop, Cursor, Anthropic, OpenAI) and by
  open-source projects with 50k to 100k+ GitHub stars (Cline, OpenCode, Aider, OpenHands).
- Agent governance has funded buyers in 2026: Geordie $30M Series A (May), Rein Security $25M (Oct),
  Comp AI $34M (Sep), Guild.ai $30M (Mar, aggregator-reported). These sell to security teams. The search found
  no coding-agent-specific one, but a small sample does not prove that gap exists.
- Platform risk is real: Claude Code already has permission modes, hooks, sandboxing and an auto mode; Microsoft
  sells Agent 365 (reported about $15 per user per month; sources disagree). Keelway must be better at three
  things they will not do well: **work across agents, run locally, and be independently verifiable.**

## 2. The owner's draft model, with one important change

Owner's draft: free local runtime, CLI and single-developer state engine; paid Cloud/Enterprise for multi-tenant
state synchronization, centralized compliance audit logs, team memory, and fleet-wide container sandboxing.

That is the right shape (open core). Guidance from the 2026 monetisation write-ups: charge for **reducing risk,
handling operations and proving compliance**, not for access to the code.

**Change:** do not make "sync the developer's state to the cloud" the default. It contradicts the local-first and
air-gap promise and is the first thing a security reviewer will reject. Use a split instead:

> **Policy flows down. Hashes flow up. Code stays local.**
> The cloud sends signed policy to each local runtime and receives only audit hashes and metadata. Full
> content sync (team memory, shared runs) is opt-in per workspace.

This gives teams central governance without exfiltrating source, which almost nobody else can claim. It also
needs verifying in code: today the Record is a local database with a verify endpoint, and there is no cloud
service, no policy distribution and no external anchoring.

| Tier | Includes | Status |
|---|---|---|
| **Free / open source** | Runtime, CLI, single-user Studio, local approvals and scoped rules, DLP, local-first router, local Record with `verify` | Mostly built |
| **Team** | Org policy sync, central Record with retention and search, SSO, shared agent catalog, spend caps, savings report | Not built |
| **Enterprise** | SCIM, SIEM export, signed attestations, managed sandboxes (container fleet), air-gapped self-host, support and SLAs, audit evidence packs | Not built |
| **Usage** | Managed model gateway: routing, caps, margin on routed cloud tokens | Router exists; no billing |

**Pricing is a hypothesis to test, not a decision.** Reference points reported by secondary sources: Cursor team
plans roughly $30 to $40 per user per month, Agent 365 about $15 per user, Agentforce about $2 per
conversation or $125 to $150 per user. A first test: free tier, Team around $20 to $30 per developer per month,
Enterprise by annual contract. Validate with 10 design-partner teams before publishing prices.

## 3. Letting people create and manage agents on the platform

The owner asked for this and it is a strong idea, but the evidence says do it in this order.

**What the evidence says (unverified, vendor-blog level):** public agent marketplaces concentrate revenue in a
small top tier; one blog reports a median of about $47 per month for individual creators, and GPT Store revenue
terms were still unpublished as of April 2026. What reportedly works is niche, high-value specialist agents,
**enterprise catalogs with negotiated terms**, and marketplace listings as lead generation. Typical creator
splits quoted are 70 to 85 percent, but that is not audited.

**So build the management layer first, the marketplace last.**

1. **Agent Manifest.** A declarative, versioned, signable file for an agent: instructions, tools (MCP servers),
   allowed paths and commands, budget, model-routing policy, sandbox profile, owner. Runs on any Keelway
   runtime. The existing approval rules and autonomy policies become the manifest's permission section.
2. **Registry and fleet view (private to a team).** Every agent has an identity, an owner, permissions, a budget
   and a kill switch. Studio's task-first home becomes the run board. This is the paid Team feature, and it is
   where the owner's "manage them" idea lives.
3. **Builder in Studio.** Create an agent from a template, test it in a sandbox, replay it from the flight
   recorder, then publish it to the team catalog.
4. **Public registry with "Keelway Verified".** Later. Verified means: permissions declared, passes a policy
   pack, audited sample runs. Only then add a revenue share. Marketplace cold start is hard, so do not open it
   before there are real users and agents.

**Protocol fit:** MCP covers agent-to-tool (an unofficial registry listed over 18,000 servers in early 2026);
A2A covers agent-to-agent (1.0 under the Linux Foundation, 150+ supporting organisations, registry still on its
roadmap). Keelway should speak both. A verified, policy-bound registry is a gap worth testing, not a proven one.

## 4. Where the moat comes from

Ordered by how defensible and how soon:

1. **The Record as an open, verifiable format** that other agents emit into (Claude Code hooks, Cursor, Codex via
   MCP/ACP). If Keelway is the system of record for agent actions, it stays valuable whichever agent wins.
2. **Policy packs** mapping SOC 2, ISO 27001, HIPAA and PCI controls to agent actions, with evidence export.
3. **Routing data.** The cost-arbitrage router learns which model is good enough for which task in your repo,
   and shows a savings report that sells the Team plan by itself.
4. **Agent identity, budgets and kill switches** for the whole fleet.
5. **Private evals:** a trust score per agent and model on your own codebase.

## 5. Licence (open decision)

Recommended: **permissive (Apache-2.0) for the runtime, CLI and the Record specification; proprietary for the
Cloud and Enterprise features.** Open code is how a young vendor earns trust from developers, and the incumbent
open-source agents are all free. A source-available or BSL-style licence (HashiCorp changed Terraform's in
August 2023 to restrict commercial competitors) trades trust for protection from cloud resellers; since the money
here is in compliance and fleet features, that trade is not worth it. The README says "proprietary" today.

## 6. Risks to say out loud

- Platform vendors bundle governance (Claude Code, Agent 365). Mitigation: cross-agent, local, verifiable.
- Funded governance startups sell to the same security buyers. Mitigation: coding-agent focus and developer
  distribution, which they lack.
- Local model quality. One source reports about 70% on SWE-bench Verified for a large open model, but other
  sources say that benchmark is saturated. The $0 inference claim holds only on larger machines (about 24 GB).
- Trust in a young vendor that sits in the security path. Needs an independent security review and a SOC 2
  programme before enterprise deals.
- Marketplace cold start and thin creator earnings. Mitigation: private catalogs first.
- A billion-dollar outcome needs an enterprise sales motion eventually. Developer love alone will not get there.

## 7. Sequence and what proves each stage

| When | Goal | Proof |
|---|---|---|
| 0 to 3 months | Make the claims true; developer distribution | P0 items in the roadmap; PyPI release; published evals; 1,000 weekly active local installs |
| 3 to 9 months | First revenue | Team tier with policy sync and central Record; 10 paying design partners; savings report |
| 9 to 24 months | Platform | Agent Manifest and registry; Record adopted by at least one third-party agent; first Enterprise contracts; SOC 2 |

The numbers in the last column are placeholders to argue about, not forecasts.

## 8. Company name: Sorvex Labs

Findings (2026-11-01; **not a trademark clearance**):

- Web search found no company or product called "Sorvex" or "Keelway", only similar names.
- DNS lookups (not WHOIS, so "no records" does not prove a domain is free): `keelway.com` and `keelway.ai`
  have DNS records (taken or parked); `keelway.dev` and `keelway.io` had no records; `sorvex.com` is registered
  (looks parked); `sorvexlabs.com` has an A record pointing at an address in a Shopify range, so check whether
  it is the owner's; `sorvex.dev` and `sorvex.ai` had no records.
- Run USPTO and CIPO searches in classes 9 and 42 for both names, and confirm domains at a registrar, before
  printing or applying.

Recommendation: **use one name, Keelway, as both company and product, and drop "Sorvex
Labs" for now.** A parent brand for "every tool" is premature with one product, "Labs" reads small (the same
problem the first brand kit had), and a second name doubles the trademark and domain work. The company can be
renamed or a holding name added later; startups often do. If the owner already owns `sorvexlabs.com` and
legal entities under that name, keep it only as the legal entity and lead with Keelway everywhere public.
