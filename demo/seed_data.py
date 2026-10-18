"""The demo world: the Tally team, its landing page, what Strata has learned, and a small catalog.

Every catalog asset is original art in `design/assets/`; nothing third-party is resold.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone


def _ago(**kw) -> str:
    return (datetime.now(timezone.utc) - timedelta(**kw)).isoformat()


MEMBERS = {
    "Priya": {"name": "Priya", "role": "lead", "fill": "#E7E1F1", "ink": "#55467A"},
    "Alex": {"name": "Alex", "role": "designer", "fill": "#DCEDE8", "ink": "#2D665C"},
    "Sam": {"name": "Sam", "role": "designer", "fill": "#F4E2E5", "ink": "#86404F"},
}

EDITABLE = {
    "heading": {"text": "string", "color": "hex", "font_size": "number", "font_weight": "number"},
    "text": {"text": "string", "color": "hex", "font_size": "number"},
    "button": {"text": "string", "bg": "hex", "color": "hex"},
    "nav": {"text": "string"},
    "illustration_slot": {},
    "icon_row": {},
}

CATALOG = [
    {"id": "seedling-jar", "title": "Seedling jar", "creator": "Ines Ward", "kind": "illustration", "style": "flat",
     "colours": 2, "palette": ["navy", "sage"], "prices": {"personal": 1200, "commercial": 2400, "extended": 6000}},
    {"id": "paper-boats", "title": "Paper boats", "creator": "Studio Pilcrow", "kind": "illustration", "style": "flat",
     "colours": 2, "palette": ["navy", "sage"], "prices": {"personal": 1600, "commercial": 3200, "extended": 7000}},
    {"id": "open-door", "title": "Open door", "creator": "Mo Rahman", "kind": "illustration", "style": "line",
     "colours": 2, "palette": ["navy", "sage"], "prices": {"personal": 900, "commercial": 1800, "extended": 4000}},
    {"id": "sunrise-ledger", "title": "Sunrise ledger", "creator": "Kettle & Co", "kind": "illustration",
     "style": "flat", "colours": 3, "palette": ["amber", "coral", "navy"],
     "prices": {"personal": 1900, "commercial": 3800, "extended": 8000}},
    {"id": "coin-stack", "title": "Coin stack", "creator": "Ines Ward", "kind": "illustration", "style": "flat",
     "colours": 3, "palette": ["navy", "mint", "gold"], "prices": {"personal": 1100, "commercial": 2200, "extended": 5000}},
    {"id": "tiny-coins", "title": "Tiny coins", "creator": "Penny Studio", "kind": "icon_set", "style": "line",
     "colours": 1, "palette": ["navy"], "prices": {"personal": 400, "commercial": 1200, "extended": 2400}},
    {"id": "soft-circles", "title": "Soft circles", "creator": "Penny Studio", "kind": "icon_set", "style": "flat",
     "colours": 2, "palette": ["navy", "mint"], "prices": {"personal": 600, "commercial": 1400, "extended": 3000}},
]


def payment_method() -> dict:
    """The team's card on file. Only the server's checkout reads it; it never goes into agent context."""
    return {"brand": "Visa", "last4": "4242", "holder": "Tally design · held by Priya",
            "token": "vtok_" + secrets.token_hex(8)}


def seed() -> dict:
    elements = {
        "nav": {"key": "nav", "name": "Nav", "kind": "nav", "order": 0,
                "props": {"text": "tally.", "links": ["Savings", "Cards", "Pricing"]},
                "locked_props": [], "locked_by": None, "authorship": "human", "last_author": "Alex"},
        "hero_heading": {"key": "hero_heading", "name": "Hero heading", "kind": "heading", "order": 1,
                         "props": {"text": "Money that waits for you.", "color": "#14254A", "font_size": 44,
                                   "font_weight": 800},
                         "locked_props": ["color"], "locked_by": "Priya", "authorship": "ai",
                         "last_author": "Strata for Alex"},
        "hero_subcopy": {"key": "hero_subcopy", "name": "Hero subcopy", "kind": "text", "order": 2,
                         "props": {"text": "Round-ups, gentle goals and no surprise fees. Your savings grow while "
                                           "you get on with your day.", "color": "#3B4A66", "font_size": 16},
                         "locked_props": [], "locked_by": None, "authorship": "human", "last_author": "Sam"},
        "cta_button": {"key": "cta_button", "name": "Primary button", "kind": "button", "order": 3,
                       "props": {"text": "Open an account", "bg": "#5FD39A", "color": "#14254A"},
                       "locked_props": [], "locked_by": None, "authorship": "human", "last_author": "Priya"},
        "hero_illustration": {"key": "hero_illustration", "name": "Hero illustration",
                              "kind": "illustration_slot", "order": 4, "props": {"asset_id": None},
                              "locked_props": [], "locked_by": None, "authorship": "ai",
                              "last_author": "Strata (pencil draft)"},
        "feature_row": {"key": "feature_row", "name": "Feature row", "kind": "icon_row", "order": 5,
                        "props": {"asset_id": "tiny-coins",
                                  "items": [["Round-ups", "Spare change, quietly saved."],
                                            ["Gentle goals", "Targets that bend with your month."],
                                            ["No surprise fees", "Every charge, in plain words."]]},
                        "locked_props": [], "locked_by": None, "authorship": "human", "last_author": "Sam"},
    }
    history = [
        {"id": "h1", "element_key": "hero_heading", "kind": "edit", "actor": "human", "author": "Alex",
         "on_behalf_of": None, "summary": "Created the heading", "at": _ago(days=6)},
        {"id": "h2", "element_key": "hero_heading", "kind": "edit", "actor": "ai", "author": "Strata",
         "on_behalf_of": "Sam", "summary": "Colour navy → warm charcoal", "ai_reason": "Sam asked for warmth.",
         "before": {"color": "#14254A"}, "after": {"color": "#3A3632"}, "status": "undone",
         "undone_by": "Priya", "rule_ids": [], "at": _ago(days=1, hours=2)},
        {"id": "h3", "element_key": "hero_heading", "kind": "edit", "actor": "human", "author": "Sam",
         "on_behalf_of": None, "summary": "Copy: “Save smarter, every day” → “Money that waits for you.”",
         "at": _ago(hours=3)},
        {"id": "h4", "element_key": "hero_heading", "kind": "lock", "actor": "human", "author": "Priya",
         "on_behalf_of": None, "summary": "Locked colour at navy", "at": _ago(hours=1, minutes=30)},
        {"id": "h5", "element_key": "hero_heading", "kind": "edit", "actor": "ai", "author": "Strata",
         "on_behalf_of": "Alex", "summary": "Size 40 → 44, weight 700 → 800",
         "ai_reason": "“More premium” here means more contrast, not a new typeface, so I kept Bricolage.",
         "before": {"font_size": 40, "font_weight": 700}, "after": {"font_size": 44, "font_weight": 800},
         "status": "kept", "rule_ids": ["r-heavy"], "at": _ago(minutes=40)},
        {"id": "h6", "element_key": "feature_row", "kind": "purchase", "actor": "human", "author": "Sam",
         "on_behalf_of": None, "summary": "Bought Tiny coins icons · personal license", "at": _ago(days=3)},
        {"id": "h7", "element_key": "hero_subcopy", "kind": "edit", "actor": "human", "author": "Sam",
         "on_behalf_of": None, "summary": "Shortened the subcopy to two lines", "at": _ago(hours=2)},
        {"id": "h8", "element_key": "hero_illustration", "kind": "edit", "actor": "ai", "author": "Strata",
         "on_behalf_of": "Priya", "summary": "Drew a pencil placeholder for the hero art",
         "ai_reason": "The hero needs a picture; I left a draft until someone picks real art.",
         "status": "kept", "rule_ids": [], "at": _ago(hours=5)},
    ]
    rules = [
        {"id": "r-navy", "text": "Headings stay navy", "scope": "team", "members": ["Priya", "Sam"],
         "kept": 7, "undone": 0, "pinned": True, "requires": {"palette_includes": "navy"}},
        {"id": "r-flat-2c", "text": "Illustrations are flat, two colours", "scope": "team",
         "members": ["Priya", "Sam"], "kept": 4, "undone": 1, "pinned": False,
         "requires": {"style": "flat", "max_colours": 2}},
        {"id": "r-heavy", "text": "Heavier headings, weight 600+", "scope": "personal", "members": ["Alex"],
         "kept": 3, "undone": 0, "pinned": False, "requires": {}},
        {"id": "r-warm", "text": "Warmer page tints?", "scope": "split", "members": ["Alex", "Priya"],
         "kept": 3, "undone": 3, "pinned": False, "requires": {}},
    ]
    return {
        "file": {"slug": "fintech-landing", "name": "Fintech landing", "version": 14, "client_work": True},
        "members": MEMBERS,
        "elements": elements,
        "history": history,
        "rules": rules,
        "catalog": CATALOG,
        "mandates": {
            "Alex": {"limit_cents": 5000, "spent_cents": 0, "allowed_licences": ["personal", "commercial"],
                     "set_by": "Priya", "expires": "2026-11-30"},
            "Sam": {"limit_cents": 3000, "spent_cents": 400, "allowed_licences": ["personal", "commercial"],
                    "set_by": "Priya", "expires": "2026-11-30"},
            "Priya": {"limit_cents": 20000, "spent_cents": 0,
                      "allowed_licences": ["personal", "commercial", "extended"], "set_by": "Priya",
                      "expires": "2026-12-31"},
        },
        "licences": [
            {"licence_id": "L-0412", "asset_id": "tiny-coins", "tier": "personal", "element_keys": ["feature_row"],
             "member": "Sam", "amount_cents": 400, "payment_ref": "seed", "status": "active", "at": _ago(days=3),
             "how": ["Bought by Sam before the file was client work", "personal license only",
                     "placed on the feature row"]},
        ],
        "payment_method": payment_method(),
        "conflicts": [],
        "shortlists": {},
        "catchups": {},
        "carts": {},
        "runs": [],
        "last_seen": {"Priya": _ago(hours=4), "Alex": _ago(hours=5), "Sam": _ago(hours=2)},
    }
