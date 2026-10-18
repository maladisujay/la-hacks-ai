# Strata · 2-minute demo video

## 0. Set up (3 minutes, once)
1. Stay on the **phone hotspot** (venue Wi-Fi has blocked agent.creao.ai).
2. Terminal 1, leave running:
   ```bash
   uv run python demo/server.py
   ```
3. Terminal 2, before **every** take (~1 min; resets the team and pre-runs the real CREAO agent):
   ```bash
   uv run python scripts/prepare_demo.py
   ```
   Venue Wi-Fi blocking CREAO? `uv run python scripts/prepare_demo.py --restore` loads the last good prepared state.
4. Chrome, full screen, window at least 1440 wide, zoom 100%: http://localhost:8044
5. Click **AL** in the top bar (you're Alex, a designer). Close other tabs and notifications.
6. Record with QuickTime (File → New Screen Recording) or OBS, mic on. Speak slowly; the lines below fit 2:00.

## 1. The video, click by click

| Time | What to click / show | What to say |
| --- | --- | --- |
| **0:00–0:10** | Start on the workspace. (Optional: 3 s of your Paper file with the screens first.) | "This is Strata, a design file for small teams with one AI teammate living in it. We designed every screen by hand in Paper first." |
| **0:10–0:22** | Tick **Show who made what** above the page. Click the **Hero heading** on the page. Point at the History panel on the right. | "Dashed blue pencil is the AI, solid ink is people. Click anything and you see who changed it, human or AI, for whom, and why." |
| **0:22–0:45** | Click the ask box at the bottom right, type `Make it warmer, try a charcoal colour`, press Enter. Show the line *"Strata is thinking… CREAO agent"*. **Pause recording / cut** until the yellow conflict card appears (~45 s). Point at the reason, then at the blue **Strata's middle ground** box. Click **Use the middle ground**: the subcopy turns warm, the heading stays navy. Click the **Hero subcopy** to show "Strata, for Alex & Priya" with the reason and Keep/Undo. | "Alex wants warmer, but Priya locked the navy. Strata won't silently override a teammate. Instead, our CREAO agent reads the team's rules and history and proposes a middle ground: warm the supporting text, keep Priya's navy. One click, both get what they wanted, it's recorded for both of them, and the team rule learns from it." |
| **0:45–0:55** | Click **Asset shop** (top right). Point at the AI note and click **What Strata saw**. Then click the **Footer app icons** chip at the top of the shop, then back to **Hero illustration**. | "Shopping happens inside the file, for any element: art, icons, backgrounds, even the footer. CREAO ranked these by what this team keeps and undoes, explains each pick, and never sees card data." |
| **0:55–1:02** | Click the **top pick** in the list: it appears on the page with a PREVIEW watermark. Point at the limit bar. Click **Review and buy**. Point at the paper trail. | "Try it on the real design before paying. Alex has a $50 monthly limit set by Priya, and every purchase leaves a paper trail." |
| **1:02–1:30** | Click **Checkout with Click to Pay**. Point at the ✓ spending rules. Click **Continue** (email is filled). Type the 6-digit code shown in the grey box, click **Verify**. Point at the greyed-out Canadian debit card. Pick **Visa Signature Business •••• 4242** → **Continue**. Tick **I agree to the Visa Click to Pay Terms** → **Pay**. Let the three steps tick, then point at **Payment approved**. Click **Done**. | "Checkout follows Visa Click to Pay. Strata checks the team's spending rules first. Visa verifies Alex with a one-time code, shows only eligible cards, and the merchant receives a Visa token and a one-time cryptogram, never the card number. Approved through VisaNet, and the license is tied to this element." |
| **1:30–1:45** | Click **Export for client** (top). In the yellow panel click **Upgrade for $8** → **Checkout with Click to Pay**. Alex is recognized, so it goes straight to the cards: pick •••• 4242 → Continue → tick Terms → **Pay** → **Done**. Point at the green "Every asset … licensed". | "Before a client export, Strata catches Sam's personal-use icons. One upgrade, and because Alex chose Remember me, Click to Pay recognizes him." |
| **1:45–1:55** | Click **PR** (Priya). Click **Catch me up** (top). Then click the **Team rules** tab. | "Priya comes back to a CREAO catch-up of what changed. Every Keep and Undo teaches the team's taste." |
| **1:55–2:00** | Close the popover; show the page. | "Strata: designed in Paper, every AI step on CREAO, checkout on Visa Click to Pay. Remove the agent and Strata stops working." |

**Too long?** Drop the export upgrade (1:30–1:45) and say the line over the yellow panel instead.
**Retake:** run `prepare_demo.py` again first; it resets the team.

## 2. Live judging (same flow, ~3 min)
Run `prepare_demo.py` 5 minutes before judges arrive. Do the conflict request first and talk through
provenance while CREAO works (~45 s). If CREAO is unreachable, use `--restore`.

## 3. If something goes wrong
- "The agent couldn't finish": CREAO unreachable or slow → retry, or `prepare_demo.py --restore`.
- Top bar says "AI: not connected": `.env` lost `CREAO_STRATA_APP_ID` / `CREAO_STRATA_KEY`; restart the server.
- Wrong code typed three times: Click to Pay starts over at the email step (by design).
