# Strata · Devpost text

**Tracks:** Visa "The Future of Shopping" · Paper "Best Designed Hack" · CREAO "AI-First Disruptor" · main track
Applied Intelligence.

**Tagline:** Every element knows who made it, why, and whether you're allowed to ship it.

## Inspiration
Design is done by teams, but AI assistants are built for one person. Shared AI forgets who decided what,
silently overrides teammates and can't explain itself. Buying design assets is just as blind: designers judge
fonts and illustrations on generic previews in separate store tabs, and license knowledge lives in someone's
inbox, so personal-use assets slip into client work.

## What it does
Strata is a shared design workspace with one AI teammate that lives in the file.
- **Provenance Lens:** click any element to see who changed it, human or AI, on whose request, and the AI's
  stated reason. The AI drafts in dashed blue pencil; people ink in solid.
- **AI teammate:** ask for a change in plain words. It edits one element, explains why, and **refuses to undo a
  teammate's locked decision**: it opens a conflict card naming both people instead. Keep or Undo on every AI
  edit teaches it the team's taste (team, personal and split rules with kept/undone counts).
- **Try-on Shop:** the Curator agent ranks the catalog by the team's learned taste, the buyer's license needs and
  spending limit, and says why for each pick. Click to try an asset on the real design (watermarked) before
  buying.
- **Checkout inside a spending limit:** the lead sets each person's monthly limit and allowed license tiers.
  Over the limit, the purchase waits for the lead's one-tap approval.
- **Licenses tied to elements + export guard:** every license records which elements it covers; before a client
  export, Strata flags personal-use assets and offers a one-click upgrade.
- **Catch me up:** a summary of what teammates and the AI changed since you last looked.

## Visa · The Future of Shopping
- **Discovery and personalization:** recommendations come from what this team keeps and undoes, and every pick
  names the rule and the teammates it was learned from.
- **Decision-making:** try-on on your own design, three license tiers explained in one line each.
- **Checkout and payments:** a review step is required; per-person spending limits and allowed tiers are checked
  when the cart is made and again at payment; over-limit purchases need the lead's approval. Payment is a
  **simulated Visa authorization** on the team's tokenized card (Visa told teams to simulate; no sandbox was
  offered). Double-submits are idempotent.
- **Post-purchase:** licenses are tied to elements, the export guard prevents misuse, upgrades are priced as the
  difference.
- **Trust and responsibility:** nothing is charged without review or above a limit; the paper trail
  (intent → cart → payment → receipt) is visible; **the AI agents never receive card data** (only rules,
  catalog and limits); every AI recommendation and edit carries its reason; the AI can't override a person's
  locked decision.
- **Commerce impact:** buyers see the asset in context before paying (fewer refunds, more confident purchases);
  creators get sales from inside the tool where the decision happens; teams stop shipping unlicensed assets.

## CREAO · AI-First Disruptor
Every AI step in Strata runs on one CREAO agent with three skills, called through CREAO's API trigger with
`request` + `context_json` (the app tells it the task); the app applies its answer:
- **Shortlist:** ranks assets against the team's learned rules, the license and the spending limit, and explains each pick.
- **Edit:** decides the smallest change to one element and writes its reason, or stops with a conflict on a teammate's lock.
- **Catch-up:** turns the change history into a short, personal summary with one open question.

Remove the agent and Strata stops working: no shortlist, no AI edits, no catch-up.
CREAO agent ID: `92cfb66e-0730-47b9-8bce-2efafab3f6c8` · Agent run: `<share link>`.

## Paper · Best Designed Hack
Every screen was designed by hand in Paper first, then built to match ("drafting table" system: the AI drafts in
dashed blue pencil, people ink in solid). Calm vellum surfaces, hairline rules, no glow or gradients, Atkinson
Hyperlegible Next for legibility, mono for prices and times, one handwritten margin note. The sample client site
("tally.") has its own brand so it never blurs with Strata's UI. We checked contrast (AA for body and meta
text), kept text at 12px or larger, and made every control keyboard-reachable with visible focus.
Paper file: `<link>` · screens in `design/screens/`.

## How we built it
Paper (design, via MCP) → FastAPI + a single hand-written page for the app → three CREAO agents for every AI
step. Simulated Visa authorization with tokenized card, mandate checks and idempotent payments.

## Challenges
We started with a multi-agent chat version on Fetch.ai and a Base44 build, then cut both to put the time into
the product people would actually use. Agent runs take minutes, so every AI step is async with a quiet progress
line, and the app double-checks locks and limits even after the agent decides.

## What we learned
Serif headings read as "AI-generated" to our testers, so we moved to a plain humanist sans. Separating the
client site's brand from the tool's UI made the provenance marks much easier to read.
<add on-site user test notes here>
