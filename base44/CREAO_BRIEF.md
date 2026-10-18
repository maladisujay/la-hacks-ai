# Strata · CREAO agents brief

**Track: Best AI-First Disruptor ($2,000).** Remove the agents and Strata stops working: the shop has no
shortlist, the AI teammate can't edit or explain anything, and nobody gets caught up.

**Split:** Base44 is the app (UI, data, Stripe checkout for Visa). CREAO agents are the brains: they read the
team's file, rules and history from Base44, do the reasoning, and write results back into Base44, which the UI
shows live. Runs take minutes, so every run is async and the UI shows progress.

```
Base44 UI ──(button)──▶ Base44 function runAgent ──API Trigger──▶ CREAO agent run
     ▲                                                               │  reads + writes Base44 entities (REST)
     └──── live entity updates ◀── Base44 function creaoWebhook ◀────┘  webhook when done
```

Without the Base44 Builder plan (no backend functions), start runs with `scripts/run_creao.py`, or from the
agent's page on agent.creao.ai. The agent still writes into Base44 and the UI still updates live.

---

## Setup (10 min)

1. Register with the hackathon link (upgraded account): community.creao.ai/AI_hackathon_UCLA2026
2. In Base44: Workspace Settings → Secrets → **Personal access tokens** → create one scoped to the Strata app
   with **Full** access. Note the app ID (Dashboard → API).
3. In CREAO: Secrets → add `BASE44_APP_ID` and `BASE44_PAT` (uppercase names; they become env vars).

## Agent 1 · Strata Curator (build first, 15 min)

Open agent.creao.ai, start a new chat, paste this, test it once, then **Create Agent**:

> You are **Strata Curator**, part of a design-team app. You pick design assets that fit a team's learned taste
> and write a ranked shortlist into the team's Base44 database.
>
> Inputs: `file_slug`, `spot_key` (e.g. "hero_illustration_slot"), `member_name`, `budget_usd`, `licence`
> (personal | commercial | extended).
>
> Use Python with `requests`. Base URL: `https://app.base44.com/api/apps/{os.environ["BASE44_APP_ID"]}/entities`.
> Header: `Authorization: Bearer {os.environ["BASE44_PAT"]}`. List with GET `/{Entity}` (filters as query
> params, e.g. `?member_name=Alex`); create with POST `/{Entity}` (JSON body); update with PUT `/{Entity}/{id}`.
>
> Steps:
> 1. GET `TasteRule`, `Asset`, `Mandate?member_name=<member_name>`.
> 2. Keep rules with scope "team", plus scope "personal" only if `member_name` is in its `members`. Ignore "split".
> 3. Score each illustration asset: for each applicable rule it satisfies add `(kept+1)/(kept+undone+2)`, for
>    each it breaks subtract the same. Rules: "Illustrations are flat, two colours" needs `style == "flat"` and
>    `colours <= 2`; "Headings stay navy" needs "navy" in `palette`. Subtract 1.5 if the price for `licence`
>    (`price_<licence>_cents`) is over the budget or over the mandate's `limit_cents - spent_cents`.
> 4. Sort by score, then cheaper first. Take the top 4.
> 5. For each, write one plain sentence (max 16 words) on why it fits or not, naming who taught the rule
>    (e.g. "Flat and two-colour, the style Priya and Sam keep choosing.").
> 6. Delete old `Shortlist` rows for this `spot_key` and `member_name`, then POST one `Shortlist` row per asset:
>    `spot_key, member_name, asset_id, rank, score, why, fits (list), breaks (list), price_cents`.
> 7. POST a `HistoryAtom`: `element_key=<spot_key>, kind="rule", actor="ai", author="Strata",
>    on_behalf_of=<member_name>, summary="Shortlisted 4 assets for <spot_key>"`.
> 8. Reply with a 2-line summary of the shortlist.

## Agent 2 · Strata Teammate (20 min)

> You are **Strata Teammate**, the AI that lives in a team's design file. You edit one element at a time, explain
> every edit, and never override a teammate's locked decision.
>
> Inputs: `element_key`, `member_name`, `request` (what the member asked for).
> Same Base44 access as above (BASE44_APP_ID, BASE44_PAT, GET/POST/PUT).
>
> Steps:
> 1. GET `DesignElement?key=<element_key>`, its last 8 `HistoryAtom?element_key=<element_key>`, and `TasteRule`.
> 2. Decide the smallest change to `props` that satisfies the request and respects team rules (team rules for
>    everyone, personal rules only for their owner, never split rules). Write a one-sentence reason first.
> 3. If any changed prop is in `locked_props`: do NOT change the element. POST a `Conflict`
>    (`element_key, prop, parties=[{member: locked_by, wants: current value}, {member: member_name, wants: new value}],
>    status="open"`) and a `HistoryAtom` (kind "conflict", actor "ai", summary "Stopped: would undo <locked_by>'s
>    locked <prop>"). Reply explaining you asked instead of overriding.
> 4. Otherwise PUT the element with the new `props`, `authorship="ai"`, `last_author="Strata"`, and POST a
>    `HistoryAtom`: `kind="edit", actor="ai", author="Strata", on_behalf_of=<member_name>, summary=<what changed>,
>    ai_reason=<reason>, before=<old props>, after=<new props>`.
> 5. Reply with the reason in one sentence.

## Agent 3 · Strata Catch-up (optional, 10 min)

> You are **Strata Catch-up**. Input: `member_name`, `since` (ISO time). GET `HistoryAtom` newer than `since`
> made by anyone other than `member_name`. Write a `CatchUp` row: `member_name`, `lines` (list of short lines like
> "Sam rewrote the hero line." / "Strata made the heading heavier for Alex."), `open_questions` (count of open
> `Conflict`). Reply with the lines.

Schedule it hourly for each member (Workflows → Scheduled runs) so catch-ups are ready when people open the file.

## Base44 changes for CREAO

Add to Base44 (prompt in `BASE44_BRIEF.md` → "Prompt 6 · CREAO wiring"):

- Entities: **Shortlist** (spot_key, member_name, asset_id, rank, score, why, fits, breaks, price_cents),
  **AgentRun** (kind: curate | teammate | catchup, status: queued | running | completed | failed, run_id,
  inputs, result_text, member_name), **CatchUp** (member_name, lines, open_questions).
- Functions (Builder plan): `base44/functions/runAgent.ts` and `base44/functions/creaoWebhook.ts`.
  Secrets: `CREAO_CURATOR_APP_ID`, `CREAO_CURATOR_KEY`, `CREAO_TEAMMATE_APP_ID`, `CREAO_TEAMMATE_KEY`,
  `CREAO_CATCHUP_APP_ID`, `CREAO_CATCHUP_KEY`, `APP_PUBLIC_URL`, `STRATA_API_SECRET`. The `capi_` keys live only
  here, never in the browser or the repo.
- UI: the Shop reads **Shortlist** (not its own ranking); "Find assets for this slot" starts a curate run and shows
  "Strata is ranking the catalog against your team's taste…" until the AgentRun completes. The teammate input
  starts a teammate run and shows the same progress line; the element, Lens and conflict card update live.

## Devpost README requirements (CREAO's one rule)

- [ ] Share link to one agent run (from the run's page on agent.creao.ai) and each **agent ID**
- [ ] Demo shows an agent running, and the pitch says it plainly:
      "Remove the CREAO agents and Strata stops working: no shortlist, no AI edits, no catch-up."
- [ ] Select the CREAO track on Devpost

## Demo line (10 seconds)

"Alex asks for art for the hero. CREAO's Curator agent reads the team's learned taste from our Base44 database,
ranks the catalog, and writes the shortlist back. The shop you see is the agent's output. Remove it and the
product has nothing to show."
