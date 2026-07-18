# Prompt: generate a `scan.json` for your repo

Paste this to an AI coding agent (Claude Code, Cursor, etc.) opened in your repository.
It investigates the code and writes `scan.json` — a high-level map, **no source or secrets**.
Then run: `python3 foglamp-local.py run scan.json`

---

Analyze THIS repository and write a foglamp "codebase scan" to `scan.json` — a map of how
the codebase works and how it uses AI. Produce ONLY the JSON below. This stays local (a tool
renders it on localhost); nothing is uploaded.

## How to investigate
- Where AI runs: generateText / streamText / generateObject / tool({...}), @ai-sdk/* providers,
  agent loops, chat.completions / messages.create. Identify the real models + providers.
- Tools models can call (search APIs, DB queries, internal functions) and external services.
- Internal services/pipelines the product owns (billing, ingestion, workers, domain services).
- Main flows: entry points (routes/webhooks/pages/CLIs), scheduled jobs (crons/queues/workers),
  the agents, the models/tools they use, and the datastores/services they read and write.

## Output contract — EXACTLY this shape
{
  "version": 1,
  "project": { "name": "<=48", "slug": "lowercase-dashed <=48", "tagline": "<=80 optional",
               "iconDomain": "favicon domain e.g. acme.com (optional)", "date": "YYYY-MM-DD" },
  "stats": { "agents": 0, "models": 0, "tools": 0, "integrations": 0 },
  "topModels":       [ { "id": "gpt-4o", "label": "GPT-4o", "domain": "openai.com" } ],
  "topTools":        [ { "id": "exa", "label": "Exa", "domain": "exa.ai" } ],
  "topIntegrations": [ { "id": "stripe", "label": "Stripe", "domain": "stripe.com" } ],
  "graph": {
    "nodes": [
      { "id": "chat", "label": "Dashboard chat", "kind": "entry", "sub": "/api/chat" },
      { "id": "agent", "label": "Support agent", "kind": "agent", "sub": "streamText",
        "sourceRef": "src/agents/support.ts:42", "detail": "Answers tickets with order lookups" },
      { "id": "gpt4o", "label": "GPT-4o", "kind": "model", "domain": "openai.com" },
      { "id": "billing", "label": "Billing service", "kind": "service", "sourceRef": "src/services/billing.ts" },
      { "id": "pg", "label": "Postgres", "kind": "store", "domain": "postgresql.org" }
    ],
    "edges": [
      { "from": "chat", "to": "agent", "kind": "triggers" },
      { "from": "agent", "to": "gpt4o", "kind": "calls" },
      { "from": "billing", "to": "pg", "kind": "writes", "label": "charges on trial end" }
    ]
  }
}

## Rules
- Caps: topModels <= 3, topTools <= 10, topIntegrations <= 10, nodes <= 60, edges <= 120.
  Aim 20-40 nodes on a substantial codebase — rich, not sparse; every node earns its place.
- Give each distinct agent its own node (<=10 agents); merge only many near-identical ones.
- kind ∈ entry | cron | agent | model | tool | service | store | external.
- Edge kind ∈ calls | reads | writes | triggers. Add an edge label only when a specific phrase
  says more (put business logic on edges, e.g. "charges on trial end"); labels are always shown.
- `group` (<=24): tag related nodes with a shared feature/domain name ("Billing", "Ingestion");
  use 2-4 groups of 3-6 nodes; leave hub-and-spoke nodes ungrouped.
- Labels <=28, sub <=40, edge labels <=24. `domain` = favicon domain, no scheme (openai.com,
  anthropic.com, exa.ai). Add it to anything a recognizable product owns; omit for internal nodes.
  Models use the product domain (claude.ai for Claude, gemini.google.com for Gemini).
- `detail` (<=200) one sentence shown on click. `sourceRef` (<=120) repo path[:line] for internal
  nodes. Every edge from/to must reference an existing node id; ids unique. Valid JSON only.
- Do NOT invent AI usage — if the product calls an external backend for the LLM, model that as an
  external service, not a local model. Use today's date for project.date.
