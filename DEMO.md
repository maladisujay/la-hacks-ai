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
| 0:55 | Click **Seedling jar** (try-on), then **Review and buy**. | "Try it on the real design. Alex has a $50 limit set by Priya, with a visible paper trail." |
| 1:02 | **Continue to Visa checkout** → point at the agent token and spend controls → **Confirm with passkey** → steps tick → **Approved** → **Done**. | "Visa Intelligent Commerce: Strata pays with its own agent token under the spend controls Priya set, Alex confirms with a passkey, the merchant verifies the agent's signed intent, and the card number is never shared." |
| 1:12 | **Export for client** → **Upgrade for $8** → **Pay** → green "Every asset … licensed". | "After purchase, Strata catches Sam's personal-use icons before they ship to a client." |
| 1:25 | Click **PR** (Priya) → **Catch me up**. Then the **Team rules** tab. | "Priya gets a CREAO catch-up of what changed. Every Keep and Undo teaches the team's taste." |
| 1:38 | Back to the workspace. | "Designed by hand in Paper, every AI step on CREAO, checkout secured by spending limits and a Visa paper trail. Remove the agent and Strata stops working." |

## If something goes wrong
- A run fails or hangs → wait for the quiet error line, ask again; or rerun `prepare_demo.py` (resets everything).
- Top bar says "AI: not connected" → `.env` lost `CREAO_STRATA_APP_ID` / `CREAO_STRATA_KEY`; restart the server.
- Changed something by mistake → `prepare_demo.py` again.
