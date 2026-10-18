# Strata · Base44 build brief

Paste the prompts below into Base44 **one at a time, in order**. Attach the Paper screen named in each
prompt (from `design/screens/`) so Base44 copies our design instead of its default look.
After each prompt: click through the result, and if something works, **freeze that file**
(More options → Freeze Files) before the next prompt. If a prompt breaks something, use **Revert**,
don't argue with it in chat.

Time box (deadline 12:00): Prompt 1 → 20 min · 2 → 30 min · 3 → 25 min · 4 → 35 min · 5 → 15 min ·
6 (CREAO) → 15 min · submit at 11:30. Build the CREAO Curator agent in parallel while Base44 generates.

---

## Prompt 1 · Foundation: app, design system, data

> Build a web app called **Strata**: a shared design workspace for small product design teams with an AI
> teammate that lives in the design file, remembers who decided what and why, and lets the team try and buy
> design assets directly on their own design.
>
> **Design system (strict, no exceptions).** Calm, hand-made, minimal, light mode only. Page background
> #F6F3EC, panels #FDFCF8, canvas well #EFEBE1, text #2A2925, secondary text #615D54, meta text #7A766C,
> 1px hairline borders #D6D0C2, input borders #8C8678. Font "Atkinson Hyperlegible Next" for everything
> (headings weight 600–700, body 400); "IBM Plex Mono" for times, prices and IDs; "Shantell Sans" only for
> handwritten human notes. Sizes 12/13/15/18/22/28px. Radius 4px on controls, 8px on panels. **No shadows,
> no gradients, no glow, no emoji.** Authorship language: anything drafted by the AI uses a **dashed** 1.25px
> border #6A90B8 with text #2F5B85 on a #E3EEF7 tint; anything made by a person uses **solid** ink #2A2925.
> Conflicts and warnings: text #85600F on #F5EAC9 with a 3px left border. Success: #3D6A3A on #E6EFDF.
> The current selection is the only yellow: #FBF0A6. People colours: Priya #E7E1F1/#55467A,
> Alex #DCEDE8/#2D665C, Sam #F4E2E5/#86404F. See the attached design system image.
>
> **Entities:**
> - **Member**: name, role (lead | designer), colour, ink_colour. Seed Priya (lead), Alex, Sam.
> - **DesignElement**: key, name, kind (nav | heading | text | button | illustration_slot | icon_row), props (object: text, color, font_size, font_weight, image_url), locked_props (list), locked_by, last_author, authorship (human | ai), order.
> - **HistoryAtom**: element_key, kind (edit | prompt | lock | purchase | conflict | rule), actor (human | ai), author (member name), on_behalf_of (member name), summary, ai_reason, before (object), after (object), created_date.
> - **TasteRule**: text, scope (team | personal | split), members (list), kept (number), undone (number), pinned (bool).
> - **Asset**: asset_id, title, creator, kind (illustration | icon_set), style, colours (number), palette (list), image (file), price_personal_cents, price_commercial_cents, price_extended_cents.
> - **Mandate**: member_name, limit_cents, spent_cents, allowed_licences (list), set_by, expires.
> - **Licence**: licence_id, asset_id, tier, element_keys (list), member_name, amount_cents, payment_ref, status (paid | personal_issue), created_date.
> - **Conflict**: element_key, prop, parties (list of {member, wants}), status (open | kept | replaced | asked).
>
> **Seed data** (create it all now): the sample client page "tally." with elements: nav ("tally." + Savings,
> Cards, Pricing); hero heading "Money that waits for you." (color #14254A, weight 800, color locked by
> Priya); hero subcopy; button "Open an account" (mint #2FD18B); hero illustration slot (empty, authorship ai);
> feature row with icons "Tiny coins" on a personal licence bought by Sam. Taste rules: "Headings stay navy"
> (team, Priya+Sam, kept 7, undone 0, pinned), "Illustrations are flat, two colours" (team, Priya+Sam, kept 4,
> undone 1), "Heavier headings, weight 600" (personal, Alex, kept 3), "Warmer page tints?" (split, Alex+Priya,
> kept 3, undone 3). Mandates: Alex $50/month (personal, commercial allowed, set by Priya, expires Nov 30);
> Sam $30/month. History for the hero heading: Alex created it (Mon); Strata for Sam proposed warm charcoal
> and Priya undid it (yesterday); Sam rewrote the copy (11:40); Priya locked colour navy (13:05); Strata for
> Alex raised size 40→44 and weight 700→800 with reason "More premium here means more contrast, not a new
> typeface" (14:32).
>
> No login screen for now: put a **"Viewing as"** member switcher (Priya / Alex / Sam avatars) in the top bar.

## Prompt 2 · Workspace and Provenance Lens  (attach `01-workspace-provenance-lens.png`)

> Build the main **Workspace** page exactly like the attached image. Top bar: "Strata" wordmark, file name
> "Fintech landing" with "v.14 · saved" in mono, "Catch me up" with a count of new changes, member avatars,
> an "Asset shop" button. Left rail (232px): **Layers** list of the DesignElements; each row shows a small
> authorship mark on the right (dashed blue line = AI, solid ink line = person); the selected row is
> highlighted #FBF0A6. Centre: the canvas well with a faint dot grid and the **tally. page** rendered from the
> DesignElements in its own brand (white page, 12px radius, soft shadow is allowed ONLY on this sample page,
> mint #E3F8EE hero band, "Bricolage Grotesque" 800 navy headings, "Plus Jakarta Sans" body, mint pill
> button). Clicking an element on the page selects it (yellow outline with corner handles).
> Right panel (368px): **Provenance** for the selected element: title, "N changes by N people · N drafted by
> Strata", tabs History / Team rules / Licences, and a vertical timeline of its HistoryAtoms, newest first.
> Each entry: a 13px circle (dashed blue for AI, person's colour with solid border for humans), who
> ("Strata, for Alex" or "Priya"), time in mono, what changed, and for AI entries the reason in italic blue
> with a dashed left border. Undone AI changes are struck through. Below the timeline: "Then and now", two
> small cards with the oldest and current version. Bottom: "Ask Strata about this element…" input.
> Selecting a different element updates the Lens.

## Prompt 3 · AI teammate, conflict card, catch-up  (attach `02-teammate-conflict.png`)

> Add the **AI teammate**. The input at the bottom of the right panel sends the request to the LLM with this
> context only: the selected element (props, locked_props, locked_by), its last 8 HistoryAtoms, the team's
> TasteRules (team rules for everyone, personal rules only for the current member, never split rules), and
> who is asking. Ask the LLM for JSON: `{"changes": {prop: value}, "reason": "one sentence"}`.
> Before applying: **if any change touches a locked prop, do not apply it.** Create a Conflict and show the
> **conflict card** from the attached image floating next to the element: "open question · hero heading
> colour", "Two of you want different things here.", one row per person with their avatar, what they want
> (the locker's row shows their note in Shantell Sans), a colour swatch, and buttons **Keep navy** (ink),
> **Try warm on a copy** (outline), **Ask Priya** (link). Otherwise apply the changes, set authorship ai, and
> log a HistoryAtom (actor ai, on_behalf_of = current member, ai_reason = the reason). Show the AI's reply in
> the panel with a dashed-blue "S" avatar.
> **Catch me up**: clicking it shows "Since you left, <name>" with one line per change made by other people
> or by Strata since this member last opened the file, each with a small authorship dot.
> When a person edits a prop the AI set, log it as an "undone" edit and add +1 to `undone` on any TasteRule
> it matches; when an AI change survives, add +1 to `kept`.

## Prompt 4 · Try-on Shop, spending limit, checkout, licences (Visa)  (attach `03`, `04`, `05` screens)

> First, install Stripe (test mode). Then build the in-file **Asset shop** as the right panel, like the attached
> images.
> 1. **Shop** (opens from the top-bar button or from the empty hero illustration slot): title "For the hero
> slot", "Hover to try one on. Nothing is bought yet." A dashed-blue note: "Ranked by your team's taste: …
> Learned from N choices by Priya and Sam." List Assets of the right kind, ranked: assets that satisfy
> "flat" style and ≤2 colours and include navy first, cheaper first on ties; show thumbnail, title, creator,
> a green "fits both team rules" or ochre "breaks 'two colours' (Priya, Sam)" line, and price in mono.
> **Hovering or clicking an asset places it in the slot on the canvas as a try-on** with a diagonal
> "PREVIEW · STRATA" watermark and a "trying on · <title>" tag. Footer: licence and price, a bar showing the
> member's Mandate ("Within your $50 monthly mandate · $26 left after this"), and "Review and buy".
> 2. **Review**: title "Buy <asset>", radio list of licences (Personal $12 "not for client work",
> Commercial $24 "this is what the file needs", Extended $60) — disable tiers not in the member's
> allowed_licences or over the remaining mandate, and say why. A **Paper trail** list: Intent (the member's
> mandate, set by Priya) ✓, Cart (licence and price, fits the mandate) ✓, Payment (pending), Receipt
> (pending). Button **Pay $24.00** → Stripe Checkout in test mode; "Test mode · nothing real is charged".
> 3. **After payment** (success page or return): verify the Stripe session is paid, then: add amount to the
> Mandate's spent_cents, create a Licence (generate licence_id like STR-0418) covering the hero slot,
> put the asset in the slot without watermark, log a HistoryAtom purchase ("Bought by Alex"), and show the
> Lens **Licenses** tab: License, Creator, Paid (mono "$24.00 · Visa 4242"), Mandate left, Covers, and
> "How it got here: Suggested by Strata from a team rule (Priya, Sam) → tried on by Alex → bought → inked".
> 4. **Export guard**: an "Export for client" button. If any element uses a personal licence, show the ochre
> banner: "before you export for a client — The 'Tiny coins' icons in the feature row are on Sam's personal
> license. Client work needs commercial." with **Upgrade for $8** (same checkout flow) and **Swap the icons**.
> Never charge without the review step, never above the mandate.

## Prompt 5 · Team rules and polish  (attach `06-team-rules.png` and `00-design-system.png`)

> Add the **Team rules** tab in the right panel like the attached image: "What Strata has learned", each rule
> with its text (16px semibold), a scope chip (outlined "Team", Alex-coloured "Only for Alex", dashed blue
> "Split"), contributor avatars, and "kept N · undone N" in mono; "pinned" on pinned rules; split rules in
> italic blue with "Strata won't apply this; it asks instead." Footer: "Team rules need two people agreeing.
> Personal rules follow one person. Split rules become questions, never edits." and a "Write a rule by hand"
> button. Then polish the whole app against the design-system image: consistent hairlines, no shadows except
> the sample page, mono numbers, the legend at the bottom of the layers rail ("Drafted by Strata, in pencil" /
> "Inked by a person"). Add a small **Reset demo** link in the top bar that restores the seed data.

## Prompt 6 · CREAO wiring  (after the CREAO agents exist, see `CREAO_BRIEF.md`)

> The AI work in Strata is done by external **CREAO agents** that read and write this app's entities. Add:
> - **Shortlist**: spot_key, member_name, asset_id, rank (number), score (number), why, fits (list),
>   breaks (list), price_cents.
> - **AgentRun**: kind (curate | teammate | catchup), status (queued | running | completed | failed), run_id,
>   inputs (object), result_text, member_name.
> - **CatchUp**: member_name, lines (list), open_questions (number).
>
> Add two backend functions with exactly the code I paste next: `runAgent` and `creaoWebhook`.
> Change the UI so it shows the agents' output, not its own logic:
> - **Shop**: "Find assets for this slot" calls `runAgent` with kind "curate" and inputs { file_slug:
>   "fintech-landing", spot_key, budget_usd, licence } for the "Viewing as" member. The shop list shows
>   **Shortlist** rows for that spot and member ordered by rank (asset image, title, price, `why`, fits/breaks
>   chips). Remove any ranking done in the frontend.
> - **AI teammate box**: sending a request calls `runAgent` with kind "teammate" and inputs { element_key,
>   request }. The element, Provenance Lens and conflict card already update from the entities.
> - **Catch-up**: shows the latest **CatchUp** row for the member; "Refresh" calls `runAgent` kind "catchup".
> - **Progress**: while the member's latest AgentRun is queued or running, show one quiet line under the
>   control in dashed-blue AI style: "Strata is working on this… (CREAO agent, usually 1–3 min)", with a small
>   mono "run abc123" and no spinner animation. On completed show `result_text` for 6 s; on failed show
>   "The agent couldn't finish. Try again." Subscribe to AgentRun, Shortlist, CatchUp, DesignElement,
>   HistoryAtom and Conflict so changes appear live.
> - **Reset demo** also clears Shortlist, AgentRun and CatchUp.
> - Keep the app's **login required** (Base44 sign-in): `runAgent` refuses signed-out visitors so nobody can
>   spend our CREAO credits. The "Viewing as" switcher stays as it is after sign-in.

Then paste `base44/functions/runAgent.ts` and `base44/functions/creaoWebhook.ts`, add the secrets listed in
`CREAO_BRIEF.md` (Dashboard → Settings → Secrets), and **publish** so the functions go live.

## If something goes wrong

- Generic look creeping in → "Use only the design system from the first prompt: no shadows, no gradients,
  Atkinson Hyperlegible Next, hairline borders #D6D0C2."
- Stripe not available (plan) → "Replace the Stripe step with a clearly labelled simulated test payment
  that still records Payment ✓ in the paper trail."
- The AI edits the wrong element → "The teammate only ever changes the selected DesignElement."

---

## Submission text (Devpost and Base44 form)

**Problem.** Design is done by teams, but AI assistants are built for one person. Shared AI forgets who
decided what, silently overrides teammates, and can't explain itself. Buying design assets is just as blind:
designers judge fonts and illustrations on generic previews in separate store tabs, and licence knowledge
lives in someone's inbox, so personal-use assets slip into client work.

**User.** Small product design teams (2–8 people) and the creators who sell assets to them.

**Solution.** Strata is a design workspace with one AI teammate that lives in the file. Click any element to
see its full lineage: who changed it, human or AI, on whose request, and why. The AI learns the team's taste
from what people keep and undo, refuses to undo a teammate's locked decision (it opens a conflict card
instead), and catches people up on what changed. Its in-file shop ranks assets by the team's learned taste,
tries them on the real design, checks the buyer's spending limit, takes payment through Stripe, and ties each
licence to the elements that use it, with an export guard for client work.

**Visa: The Future of Shopping.** Discovery and personalization come from the team's learned rules; the
decision happens on your own design (try-on); checkout is in the file with a per-person spending limit set by
the lead; post-purchase, every licence is tied to the elements it covers and the export guard prevents misuse.
Trust is designed in: nothing is charged without a review step or above a limit, every recommendation says
which rule and which teammates it came from, and the paper trail (intent → cart → payment → receipt) is
visible. Payments run on Stripe test mode with a Visa test card.

**CREAO: AI-First Disruptor.** The reasoning in Strata is done by CREAO agents, not the app. The Curator
agent reads the team's learned rules, the buyer's spending limit and the catalog from our Base44 database,
ranks the assets and writes the shortlist back; the Teammate agent edits one element at a time, writes its
reason into the element's history, and opens a conflict card instead of undoing a locked choice; the Catch-up
agent summarises what changed for each person. Remove the agents and Strata has no shop shortlist, no AI
edits and no catch-up. Agent run: <share link> · Agent IDs: Curator <id>, Teammate <id>, Catch-up <id>.

**Paper: Best Designed Hack.** Every screen was designed by hand in Paper first ("drafting table" system:
the AI drafts in dashed blue pencil, people ink in solid) and then built in Base44 from those designs.
Paper file: <link> · screens in `design/screens/`.

**What we learned / changed.** We started with a multi-agent chat version on Fetch.ai, then cut it to put
the time into the product people would actually use: the shared workspace, with CREAO agents doing the
reasoning behind it. We moved from serif headings to a
plain humanist sans after feedback that serifs read as "AI-generated", and we separated the sample client
site's brand from Strata's own UI so the two never blur. <add on-site user test notes here>
