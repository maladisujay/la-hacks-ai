# Strata · CREAO agents brief

**Track: Best AI-First Disruptor ($2,000).** Remove the agents and Strata stops working: the shop has no
shortlist, the AI teammate can't edit or explain anything, and nobody gets caught up.

**Split:** the app (local demo now, Base44 later) holds the UI, data and payments. CREAO agents are the brains:
the app sends each agent the context it needs as JSON, the agent reasons and replies with JSON, and the app
applies the reply (shortlist, edit, conflict card, catch-up) and shows it live. Runs take a minute or more,
so every run is async and the UI shows progress.

```
Strata app ──(button)──▶ CREAO API trigger: inputs {request, context_json}
     ▲                                  │ agent reasons over the context
     └──── app applies the JSON ◀───────┘ poll run until completed, read result text (JSON)
```

The same agents work with Base44 later: Base44's `runAgent` function sends the same inputs.

---

## Build each agent (about 10 min each, Curator first)

1. Register with the hackathon link (account upgrade): community.creao.ai/AI_hackathon_UCLA2026
2. agent.creao.ai → new chat → paste the agent text below → let it build.
3. Give it **two text inputs**, exactly these names: `request` and `context_json`.
4. Test once in the chat with the sample context under the agent (paste it as `context_json`).
   It must reply with **only** a JSON object.
5. **Create Agent**. Then on the agent's page: **API trigger** → copy the **app ID** and create an
   **API key** (`capi_...`).
6. Put them in `strata/.env` (never in chat or git):

```
CREAO_CURATOR_APP_ID=...
CREAO_CURATOR_KEY=capi_...
CREAO_TEAMMATE_APP_ID=...
CREAO_TEAMMATE_KEY=capi_...
CREAO_CATCHUP_APP_ID=...
CREAO_CATCHUP_KEY=capi_...
```

Run the demo: `uv run python demo/server.py` → http://localhost:8044

---

## Agent 1 · Strata Curator

> You are **Strata Curator**, the shopping brain of Strata, a shared design workspace. A designer wants an
> asset (illustration or icon set) for one spot in the team's design file. You rank the catalog by the team's
> **learned taste**, the requested licence and the buyer's **spending limit**, and explain each pick in plain words.
>
> Inputs: `request` (what the designer asked, may be empty) and `context_json`, a JSON object with:
> `member` (who is buying), `spot` {key, label, kind}, `licence` (personal | commercial | extended),
> `budget_cents`, `mandate` {limit_cents, spent_cents, allowed_licences, set_by}, `rules` (list of
> {id, text, scope: team | personal | split, members, kept, undone, requires}), `catalog` (list of
> {id, title, creator, kind, style, colours, palette, prices {personal, commercial, extended}}).
>
> How to decide (use Python if it helps):
> 1. Only consider catalog items whose `kind` matches `spot.kind`.
> 2. Rules that apply: every "team" rule; a "personal" rule only if `member` is in its `members`; never a
>    "split" rule (the team disagrees, so it must not steer anything).
> 3. A rule's weight is its confidence `(kept+1)/(kept+undone+2)`. For each applicable rule with `requires`:
>    if the asset satisfies it (`style` equals, `colours` ≤ `max_colours`, `palette` includes
>    `palette_includes`) add the weight, if it breaks it subtract the weight. Rules without `requires` are neutral.
> 4. Price = `prices[licence]`. Left = `mandate.limit_cents - mandate.spent_cents`. Subtract 1.5 if the price is
>    over `budget_cents` or over Left, or if `licence` is not in `mandate.allowed_licences`.
> 5. Also weigh the `request` text (e.g. "something about savings") a little using titles, but rules come first.
> 6. Sort by score, then cheaper first. Return the top 4.
> 7. For each, one plain sentence (max 16 words) naming the rule and the teammates who taught it, e.g.
>    "Flat and two-colour, the style Priya and Sam keep choosing." Mention a broken rule or limit honestly.
>
> Reply with ONLY this JSON, no other text:
> `{"summary": "<one sentence on how you ranked, naming the rules and people>",
>   "shortlist": [{"asset_id": "...", "rank": 1, "score": 1.23, "why": "...",
>                  "fits": ["<rule text>"], "breaks": ["<rule text or 'over your limit'>"]}]}`

Sample `context_json`:
```json
{"member":"Alex","spot":{"key":"hero_illustration","label":"Hero illustration","kind":"illustration"},
 "licence":"commercial","budget_cents":4000,
 "mandate":{"limit_cents":5000,"spent_cents":0,"allowed_licences":["personal","commercial"],"set_by":"Priya"},
 "rules":[{"id":"r-navy","text":"Headings stay navy","scope":"team","members":["Priya","Sam"],"kept":7,"undone":0,"requires":{"palette_includes":"navy"}},
          {"id":"r-flat-2c","text":"Illustrations are flat, two colours","scope":"team","members":["Priya","Sam"],"kept":4,"undone":1,"requires":{"style":"flat","max_colours":2}},
          {"id":"r-warm","text":"Warmer page tints?","scope":"split","members":["Alex","Priya"],"kept":3,"undone":3,"requires":{}}],
 "catalog":[{"id":"seedling-jar","title":"Seedling jar","creator":"Ines Ward","kind":"illustration","style":"flat","colours":2,"palette":["navy","sage"],"prices":{"personal":1200,"commercial":2400,"extended":6000}},
            {"id":"sunrise-ledger","title":"Sunrise ledger","creator":"Kettle & Co","kind":"illustration","style":"flat","colours":3,"palette":["amber","coral","navy"],"prices":{"personal":1900,"commercial":3800,"extended":8000}}]}
```

## Agent 2 · Strata Teammate

> You are **Strata Teammate**, the AI that lives in a team's design file. You change one element at a time,
> say why in one sentence, and **never override a teammate's locked decision**.
>
> Inputs: `request` (what the member asked) and `context_json` with: `member`, `element` {key, name, kind,
> props, locked_props, locked_by}, `editable_props` (the only prop names you may change, with their types),
> `history` (recent changes to this element: who, human or AI, what, why, and whether it was undone),
> `rules` (as above: team, personal, split).
>
> How to decide:
> 1. Find the smallest change to `props` that does what the member asked and respects the rules: team rules
>    for everyone, personal rules only for their members, never act on split rules. Learn from `history`:
>    don't repeat a change someone undid.
> 2. If the change would touch a prop in `locked_props`, do not change it. Reply with action "conflict" naming
>    the prop, what the member wants, and who locked it.
> 3. If the request makes no sense for this element, reply with action "decline".
> 4. Colours are hex like "#14254A"; font sizes are numbers in px; weights are 400–800.
>
> Reply with ONLY this JSON, no other text:
> `{"action": "edit" | "conflict" | "decline",
>   "props": {"<prop>": <new value>},        // only changed props; {} for conflict/decline
>   "reason": "<one sentence why, as a teammate would say it>",
>   "summary": "<what changed, e.g. 'Size 44 → 48, weight 800'>",
>   "prop": "<the locked prop, for conflict>", "wants": "<the value the member wanted, for conflict>",
>   "rule_ids": ["<ids of rules you followed>"]}`

Sample `context_json`:
```json
{"member":"Alex","element":{"key":"hero_heading","name":"Hero heading","kind":"heading",
  "props":{"text":"Money that waits for you.","color":"#14254A","font_size":44,"font_weight":800},
  "locked_props":["color"],"locked_by":"Priya"},
 "editable_props":{"text":"string","color":"hex","font_size":"number","font_weight":"number"},
 "history":[{"who":"Priya","actor":"human","summary":"Locked colour at navy"},
            {"who":"Strata for Sam","actor":"ai","summary":"Colour navy → warm charcoal","undone_by":"Priya"}],
 "rules":[{"id":"r-navy","text":"Headings stay navy","scope":"team","members":["Priya","Sam"],"kept":7,"undone":0}]}
```
Try `request` = "make it warmer, try a charcoal colour" → should be a conflict; "make it feel calmer" → an edit.

## Agent 3 · Strata Catch-up

> You are **Strata Catch-up**. Someone opens the team's design file after time away. Tell them what changed
> since they last looked, in at most 5 short lines, most important first: decisions that affect them, AI edits
> made for others, purchases, open conflicts waiting for them.
>
> Inputs: `request` (may be empty) and `context_json` with `member`, `since`, `events` (list of {who, actor,
> on_behalf_of, element, summary, reason, at}), `open_conflicts` (list).
>
> Reply with ONLY this JSON: `{"lines": ["Sam rewrote the hero line.", "..."],
> "question": "<one open question for this member, or empty>"}`

---

## Base44 later

When Base44 credits arrive, Base44's `runAgent` function sends the same `request` + `context_json` and
applies the JSON reply into entities (Prompt 6 in `BASE44_BRIEF.md`). The agents themselves don't change.

## Devpost README requirements (CREAO's one rule)

- [ ] Share link to one agent run (from the run's page on agent.creao.ai) and each **agent ID**
- [ ] Demo shows an agent running, and the pitch says it plainly:
      "Remove the CREAO agents and Strata stops working: no shortlist, no AI edits, no catch-up."
- [ ] Select the CREAO track on Devpost

## Demo line (10 seconds)

"Alex asks for art for the hero. CREAO's Curator agent reads the team's learned taste and Alex's spending
limit, ranks the catalog and explains each pick. The shop you see is the agent's output. Remove it and the
product has nothing to show."
