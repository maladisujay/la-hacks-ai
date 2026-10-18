# Strata · design asset concierge

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

Shop for illustrations and icons **for one specific part of your team's design**, without leaving the chat.

**Try:** "Find art for our landing page hero, under $40"

What happens, all inside ASI:One:

1. **Pick the spot.** A card shows your real design file and its open spots (empty slots, licence problems).
2. **Confirm the brief.** Style, budget and licence are prefilled from rules your team taught Strata.
3. **Compare on your design.** Each option is shown placed on your own page, watermarked.
4. **Look closer.** Details, why it fits your team's taste, and a licence choice.
5. **Approve.** Your spending limit is checked before anything is charged.
6. **Pay.** Payment Protocol with Stripe; the agent never sees your card.
7. **Receipt.** The asset is placed on the file, the licence is tied to the elements that use it, and the next fix is suggested.

Behind the Concierge, four agents do the work: Curator (taste ranking), Renderer (try-on previews),
Checkout (spending limit and Stripe), and Ledger (placement and licence history). Orchestration is a
LangGraph graph with human-in-the-loop steps; the language model is ASI:One.
