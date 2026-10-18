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
Strata's checkout simulates **Visa Intelligent Commerce** end to end (Visa offered no sandbox and asked teams to
simulate):
- **Discovery and personalization:** CREAO ranks illustrations, icon sets and background patterns for whichever
  element you're working on, by what this team keeps and undoes; every pick names the rule and who taught it.
- **Decision-making:** try any asset on the real page (hero art, background, icons, section art), compare three
  license tiers, see your remaining limit before you commit.
- **Checkout:** a Visa checkout sheet shows the merchant, order, card, and the **agent token** Strata pays with
  (created by the lead with a Visa Payment Passkey) plus its **spend controls**: monthly limit, allowed license
  tiers, design assets only, expiry. Over a control, the lead approves that one purchase.
- **Payments:** the buyer confirms with a **passkey**; the merchant verifies Strata's **signed agent intent**
  (Trusted Agent Protocol); the agent token is used with a one-time cryptogram; risk check; issuer response `00`
  with auth code and Visa transaction ID. Spend controls are re-checked at authorization and decline with real
  response codes (`61` exceeds spend control, `57` not permitted, `54` expired instruction). Double-submits are
  idempotent.
- **Post-purchase:** each license is tied to the elements it covers, with an export guard for client work and
  one-click upgrades priced as the difference.
- **Trust and responsibility:** nothing is charged without review and a passkey; the AI agents never receive card
  data (a "What Strata saw" box lists exactly what each agent was sent); every recommendation and edit carries its
  reason; the AI can't override a teammate's locked decision.
- **Commerce impact:** buyers see the asset in context before paying (more confident purchases, fewer refunds);
  creators sell inside the tool where the decision happens; teams stop shipping unlicensed assets.

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
