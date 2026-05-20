MARKET_KIND_ALIASES = {
    "currency": "forex",
    "currencies": "forex",
    "forex": "forex",
    "fx": "forex",
    "otc": "otc",
    "commodity": "commodities",
    "commodities": "commodities",
    "metal": "commodities",
    "metals": "commodities",
    "stock": "stocks",
    "stocks": "stocks",
    "crypto": "crypto",
    "cryptocurrency": "crypto",
}


def normalize_stream_market_kind(value: str) -> str:
    raw = str(value or "").strip().lower()
    return MARKET_KIND_ALIASES.get(raw, raw)


def normalize_stream_asset_key(value: str) -> str:
    raw = str(value or "").strip().lower()
    for token in ("otc", "spot"):
        raw = raw.replace(token, "")
    return "".join(ch for ch in raw if ch.isalnum())


def stream_requested_asset_matches(
    settings: dict,
    analysis_type: str,
    requested_symbol: str,
    requested_market: str = "",
) -> bool:
    emulation_symbol = str(settings.get("emulation_symbol") or "").strip()
    if not emulation_symbol:
        return True

    admin_key = normalize_stream_asset_key(emulation_symbol)
    request_key = normalize_stream_asset_key(requested_symbol)
    if not admin_key or not request_key or admin_key != request_key:
        return False

    if str(analysis_type or "").strip().lower() == "binary":
        emulation_market = str(settings.get("emulation_market") or "").strip()
        if emulation_market and requested_market:
            return normalize_stream_market_kind(emulation_market) == normalize_stream_market_kind(requested_market)
    return True
