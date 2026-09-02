from typing import Any

# TODO: replace this keyword matcher with an LLM categorization call
# (provider via LLM_PROVIDER) once category labels and examples are finalized.

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Travel Expense": (
        "uber",
        "ola",
        "lyft",
        "taxi",
        "cab",
        "airline",
        "airways",
        "flight",
        "airport",
        "hotel",
        "marriott",
        "hilton",
        "airbnb",
        "booking.com",
        "makemytrip",
        "irctc",
        "train",
        "petrol",
        "diesel",
        "fuel",
        "parking",
        "toll",
    ),
    "Office Supplies": (
        "stationery",
        "staples",
        "office depot",
        "paper",
        "printer",
        "toner",
        "ink cartridge",
        "pen",
        "notebook",
        "folder",
        "stapler",
        "mouse",
        "keyboard",
        "monitor",
    ),
    "Meals & Entertainment": (
        "restaurant",
        "cafe",
        "coffee",
        "starbucks",
        "swiggy",
        "zomato",
        "doordash",
        "uber eats",
        "lunch",
        "dinner",
        "meal",
    ),
    "Software & Subscriptions": (
        "saas",
        "subscription",
        "aws",
        "azure",
        "google cloud",
        "github",
        "slack",
        "notion",
        "microsoft 365",
        "adobe",
        "zoom",
    ),
    "Identity Verification": (
        "aadhaar",
        "pan",
        "passport",
        "kyc",
        "identity",
        "id verification",
    ),
}


def categorize(extracted_data: dict, doc_type: str) -> str:
    """Assign a category using keyword rules on vendor/merchant names and items."""
    kind = (doc_type or "").strip().lower().replace(" ", "_")
    if kind in {"kyc", "kycdocument", "kyc_document"}:
        return "Identity Verification"

    haystack = _search_text(extracted_data or {})
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return category

    if kind in {"invoice", "receipt"}:
        return "Uncategorized"
    return "Uncategorized"


def _search_text(extracted_data: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("vendor_name", "merchant_name", "category"):
        value = extracted_data.get(key)
        if isinstance(value, str):
            parts.append(value)

    for collection_key in ("line_items", "items"):
        items = extracted_data.get(collection_key) or []
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                description = item.get("description")
                if isinstance(description, str):
                    parts.append(description)
            elif isinstance(item, str):
                parts.append(item)

    return " ".join(parts).lower()
