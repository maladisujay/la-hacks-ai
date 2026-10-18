# Demo script (video 1:45 · live judging the same)

## Before each take
```bash
uv run python demo/server.py            # terminal 1, leave running
uv run python scripts/prepare_demo.py   # terminal 2, ~1 min: resets the team, pre-runs CREAO
```
Open http://localhost:8044, browser full screen (1440 wide or more), click **AL** (view as Alex).

## Shots
| Time | Do | Say |
| --- | --- | --- |
| 0:00 | (Optional 3 s: the Paper file with the screens) Show the workspace. Tick **Show who made what**. | "Design teams share files, but AI assistants are built for one person. Strata puts one AI teammate in the file. Dashed blue pencil is the AI, solid ink is people." |
| 0:12 | Click the **Hero heading**. Point at the history. | "Every element knows who changed it, human or AI, for whom, and why." |
| 0:20 | Type `Make it warmer, try a charcoal colour` in the ask box, Enter. Show the line "Strata is thinking… CREAO agent". **Cut the wait (~45 s).** | "Every AI step runs on our CREAO agent." |
| 0:28 | The conflict card appears. | "Priya locked the navy. Strata won't silently override a teammate; it stops and asks." |
| 0:38 | Click **Asset shop**. Open **What Strata saw**. | "Shopping starts in the file. CREAO ranked the catalog by what this team keeps and undoes, explains every pick, and never sees card details." |
| 0:50 | (Optional) switch the **For the …** picker to *hero background* and click a pattern to show it works for any element; switch back. | "Any element: art, icons, backgrounds." |
| 0:55 | Click the **top pick** (try-on), then **Review and buy**. | "Try it on the real design. Alex has a $50 limit set by Priya, with a visible paper trail." |
| 1:02 | **Checkout with Click to Pay** → spending rules ✓ → email → type the 6-digit code shown → pick **Visa •••• 4242** (the Canadian debit card is greyed out) → tick the Visa Terms → **Pay** → approved → **Done**. | "Checkout runs on Visa Click to Pay: Strata checks Tally's spending rules first, Visa verifies Alex with a one-time code, the merchant gets a Visa token and a one-time cryptogram, never the card number, and the payment is authorized through VisaNet." |
| 1:12 | **Export for client** → **Upgrade for $8** → **Pay** → green "Every asset … licensed". | "After purchase, Strata catches Sam's personal-use icons before they ship to a client." |
| 1:25 | Click **PR** (Priya) → **Catch me up**. Then the **Team rules** tab. | "Priya gets a CREAO catch-up of what changed. Every Keep and Undo teaches the team's taste." |
| 1:38 | Back to the workspace. | "Designed by hand in Paper, every AI step on CREAO, checkout on Visa Click to Pay with team spending rules. Remove the agent and Strata stops working." |

## If something goes wrong
- A run fails or hangs → wait for the quiet error line, ask again; or rerun `prepare_demo.py` (resets everything).
- Top bar says "AI: not connected" → `.env` lost `CREAO_STRATA_APP_ID` / `CREAO_STRATA_KEY`; restart the server.
- Changed something by mistake → `prepare_demo.py` again.

Second purchase (export guard upgrade): "Remember me" was ticked, so Click to Pay recognizes Alex and goes straight
to the card list, as a returning-user flow should.
