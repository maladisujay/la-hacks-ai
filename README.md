# Strata

**Every element knows who made it, why, and whether you're allowed to ship it.**

Strata is a shared design workspace for small product teams, with one AI teammate that lives in the file.
It remembers who decided what and why, learns the team's taste from what people keep and undo, refuses to
silently override a teammate, and lets the team try and buy design assets directly on their own design,
inside a spending limit, with every licence tied to the elements that use it.

Built for LA Hacks AI Hackathon 2026 · Base44 "Build Something People Want" · Visa "The Future of Shopping" ·
Paper "Best Designed Hack" · CREAO "AI-First Disruptor" · main track: Applied Intelligence.

![Workspace and Provenance Lens](design/screens/01-workspace-provenance-lens.png)

## What's in this repo

| Path | What |
| --- | --- |
| `design/screens/` | The UI designed by hand in Paper: design system and six product screens |
| `design/tokens.css` | Design tokens exported from Paper ("drafting table" system) |
| `design/assets/` | Original illustrations and icon sets sold in the demo catalog (drawn by us) |
| `base44/BASE44_BRIEF.md` | The step-by-step prompts used to build the app in Base44, plus submission text |
| `base44/entities/` | Entity schemas for the Base44 app |
| `base44/CREAO_BRIEF.md` | The three CREAO agents (Curator, Teammate, Catch-up): specs, setup, wiring |
| `base44/functions/runAgent.ts`, `creaoWebhook.ts` | Base44 functions that start CREAO runs and receive their results |
| `scripts/run_creao.py` | Start a CREAO agent run from the command line |
| `base44/functions/agentApi.ts` | Backend function contract for external agents (optional) |
| `docs/Strata_Project_Brief.pdf` | Project brief: problem, features, method |
| `strata_agents/` | Prototype: multi-agent ASI:One shopping flow (Fetch.ai uAgents + LangGraph). Not part of this submission |

## The idea in one screen each

| Screen | What it shows |
| --- | --- |
| Provenance Lens | Click any element: who changed it, human or AI, on whose request, and the AI's stated reason |
| Conflict card | The AI won't undo a teammate's locked choice; it names both people and asks |
| Try-on Shop | Assets ranked by the team's learned taste, previewed on the real design, watermarked |
| Review and pay | Licence choice, the buyer's spending limit, intent → cart → payment → receipt trail |
| Licences and export guard | Each licence tied to its elements; personal-use assets flagged before client export |
| Team rules | What Strata learned, who taught it, team vs personal vs split |

## CREAO agents

The AI in Strata is three CREAO agents. Base44 holds the UI, data and payments; the agents do the reasoning
and write their results back into Base44, which the app shows live.

| Agent | Agent ID | What it does |
| --- | --- | --- |
| Strata Curator | `<agent id>` | Ranks the catalog against the team's learned taste, licence and spending limit; writes the shop shortlist |
| Strata Teammate | `<agent id>` | Edits one element, records its reason in the element's history, opens a conflict instead of undoing a locked choice |
| Strata Catch-up | `<agent id>` | Summarises what teammates and the AI changed since you last looked |

Example agent run: `<share link>`

Remove the agents and Strata stops working: the shop has no shortlist, the AI can't edit or explain, and
nobody gets caught up.

```
Base44 UI → runAgent → CREAO API trigger → agent reads/writes Base44 entities → creaoWebhook → live UI
```

## Design language

The AI drafts in **dashed blue pencil**; people **ink** in solid. Calm vellum surfaces, hairline rules, no
shadows or glow, Atkinson Hyperlegible Next for legibility. The sample client site ("tally.") has its own
brand so it never blurs with Strata's UI. Research basis: calm technology (Weiser & Brown), smallest effective
difference (Tufte), low-saturation colour (Valdez & Mehrabian), and sketchy drafts inviting critique
(Wong; Schumann; Tohidi).

## Payments

Stripe test mode with a Visa test card (`4242 4242 4242 4242`). Nothing real is charged.

## Prototype agents (not submitted)

`strata_agents/` contains a five-agent version of the shopping flow for ASI:One (Concierge, Curator,
Renderer, Checkout, Ledger) orchestrated with LangGraph. To try it locally:

```bash
uv sync && cp .env.example .env
uv run pytest -q
```
