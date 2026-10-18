"""Demo world: the Tally team, its file, the rules Strata has learned, and a small catalog.

Every paid asset here is original work drawn by `render.py`; nothing third-party is resold.
"""

TEAM = {
    "id": "tally",
    "name": "Tally design",
    "members": {
        "priya": {"name": "Priya", "role": "lead"},
        "alex": {"name": "Alex", "role": "designer"},
        "sam": {"name": "Sam", "role": "designer"},
    },
}

# Intent mandates: what each member may spend without asking the lead.
MANDATES = {
    "alex": {
        "member_id": "alex",
        "limit_cents": 5000,
        "period": "month",
        "spent_cents": 0,
        "allowed_licences": ["personal", "commercial"],
        "set_by": "priya",
        "expires": "2026-11-30",
    },
    "sam": {
        "member_id": "sam",
        "limit_cents": 3000,
        "period": "month",
        "spent_cents": 0,
        "allowed_licences": ["personal", "commercial"],
        "set_by": "priya",
        "expires": "2026-11-30",
    },
}

FILES = {
    "fintech-landing": {
        "id": "fintech-landing",
        "name": "Fintech landing",
        "team_id": "tally",
        "frames": ["desktop", "mobile"],
        "heading": "Money that waits for you.",
        "placements": {},  # spot_id -> asset_id once something is licensed
        "spots": [
            {
                "id": "hero-art",
                "label": "Hero art",
                "kind": "illustration",
                "status": "empty",
                "note": "empty slot",
                "frames": ["desktop", "mobile"],
            },
            {
                "id": "feature-icons",
                "label": "Feature icons",
                "kind": "icon-set",
                "status": "licence-issue",
                "note": "personal licence",
                "current_asset": "tiny-coins",
                "current_licence": "personal",
                "frames": ["desktop"],
            },
            {
                "id": "mobile-hero",
                "label": "Mobile hero",
                "kind": "illustration",
                "status": "empty",
                "note": "same slot, phone",
                "frames": ["mobile"],
            },
        ],
    }
}

# Output of LACE "weigh": rules learned from what the team kept and undid.
RULES = [
    {
        "id": "r-navy",
        "text": "Headings stay navy",
        "scope": "team",
        "applies_to": "palette",
        "requires": {"palette_includes": "navy"},
        "members": ["priya", "sam"],
        "kept": 7,
        "undone": 0,
    },
    {
        "id": "r-flat-2c",
        "text": "Illustrations are flat, two colours",
        "scope": "team",
        "applies_to": "illustration",
        "requires": {"style": "flat", "max_colours": 2},
        "members": ["priya", "sam"],
        "kept": 4,
        "undone": 1,
    },
    {
        "id": "r-heavy-headings",
        "text": "Heavier headings, weight 600",
        "scope": "personal",
        "applies_to": "type",
        "requires": {},
        "members": ["alex"],
        "kept": 3,
        "undone": 0,
    },
    {
        "id": "r-warm-tints",
        "text": "Warmer page tints?",
        "scope": "split",
        "applies_to": "palette",
        "requires": {},
        "members": ["alex", "priya"],
        "kept": 3,
        "undone": 3,
    },
]

LICENCE_LABELS = {
    "personal": "Personal · not for client work",
    "commercial": "Commercial · site and app",
    "extended": "Extended · print and merchandise",
}

CATALOG = [
    {
        "id": "seedling-jar",
        "title": "Seedling jar",
        "creator": "Ines Ward",
        "kind": "illustration",
        "style": "flat",
        "colours": 2,
        "palette": ["navy", "sage"],
        "tags": ["savings", "growth", "jar", "coins"],
        "prices": {"personal": 1200, "commercial": 2400, "extended": 6000},
        "files": "SVG, PNG at 4x",
    },
    {
        "id": "paper-boats",
        "title": "Paper boats",
        "creator": "Studio Pilcrow",
        "kind": "illustration",
        "style": "flat",
        "colours": 2,
        "palette": ["navy", "sage"],
        "tags": ["journey", "calm", "water"],
        "prices": {"personal": 1600, "commercial": 3200, "extended": 7000},
        "files": "SVG, PNG at 4x",
    },
    {
        "id": "open-door",
        "title": "Open door",
        "creator": "Mo Rahman",
        "kind": "illustration",
        "style": "line",
        "colours": 2,
        "palette": ["navy", "sage"],
        "tags": ["welcome", "start", "door"],
        "prices": {"personal": 900, "commercial": 1800, "extended": 4000},
        "files": "SVG",
    },
    {
        "id": "sunrise-ledger",
        "title": "Sunrise ledger",
        "creator": "Kettle & Co",
        "kind": "illustration",
        "style": "flat",
        "colours": 3,
        "palette": ["amber", "coral", "navy"],
        "tags": ["morning", "growth", "sun"],
        "prices": {"personal": 1900, "commercial": 3800, "extended": 8000},
        "files": "SVG, PNG at 4x",
    },
    {
        "id": "coin-stack",
        "title": "Coin stack",
        "creator": "Ines Ward",
        "kind": "illustration",
        "style": "flat",
        "colours": 3,
        "palette": ["navy", "mint", "gold"],
        "tags": ["savings", "coins", "money"],
        "prices": {"personal": 1100, "commercial": 2200, "extended": 5000},
        "files": "SVG, PNG at 4x",
    },
    {
        "id": "tiny-coins",
        "title": "Tiny coins",
        "creator": "Sam's pick · Penny Studio",
        "kind": "icon-set",
        "style": "line",
        "colours": 1,
        "palette": ["navy"],
        "tags": ["icons", "coins"],
        "prices": {"personal": 400, "commercial": 1200, "extended": 2400},
        "files": "SVG, 24 icons",
    },
    {
        "id": "soft-circles",
        "title": "Soft circles",
        "creator": "Penny Studio",
        "kind": "icon-set",
        "style": "flat",
        "colours": 2,
        "palette": ["navy", "mint"],
        "tags": ["icons", "fintech"],
        "prices": {"personal": 600, "commercial": 1400, "extended": 3000},
        "files": "SVG, 36 icons",
    },
]
