from typing import Any, Dict, List, Optional, Tuple


TwelveSymbol = Tuple[str, Optional[str]]


FOREX_STOCK_SYMBOLS: List[Tuple[str, str]] = [
    ("Advanced Micro Devices", "AMD"),
    ("Alibaba", "BABA"),
    ("Amazon", "AMZN"),
    ("American Express", "AXP"),
    ("Apple", "AAPL"),
    ("Boeing Company", "BA"),
    ("Cisco", "CSCO"),
    ("Citigroup Inc", "C"),
    ("Coinbase Global", "COIN"),
    ("Exxon Mobil", "XOM"),
    ("Facebook Inc", "META"),
    ("FedEx", "FDX"),
    ("GameStop Corp", "GME"),
    ("Intel", "INTC"),
    ("Johnson & Johnson", "JNJ"),
    ("Marathon Digital Holdings", "MARA"),
    ("McDonald's", "MCD"),
    ("Microsoft", "MSFT"),
    ("Netflix", "NFLX"),
    ("NVIDIA", "NVDA"),
    ("Palantir Technologies", "PLTR"),
    ("Pfizer Inc", "PFE"),
    ("Tesla", "TSLA"),
    ("Visa", "V"),
    ("VIX", "VIXY"),
]

CUSTOM_FOREX_CURRENCY_ASSETS: List[Dict[str, str]] = [
    {
        "pair": "AUDUSD",
        "asset": "AUDUSD",
        "symbol": "AUDUSD",
        "name": "AUDUSD",
        "label": "AUDUSD",
        "market": "currencies",
    },
]

CUSTOM_FOREX_INDEX_ASSETS: List[Dict[str, str]] = [
    {
        "pair": "SP500",
        "asset": "SP500",
        "symbol": "SP500",
        "name": "SP500",
        "label": "SP500",
        "market": "indices",
        "country": "US",
        "exchange": "TVC",
    },
    {
        "pair": "DAX",
        "asset": "DAX",
        "symbol": "DAX",
        "name": "DAX",
        "label": "DAX",
        "market": "indices",
        "country": "DE",
        "exchange": "TVC",
    },
    {
        "pair": "NIKKEI",
        "asset": "NIKKEI",
        "symbol": "NIKKEI",
        "name": "NIKKEI",
        "label": "NIKKEI",
        "market": "indices",
        "country": "JP",
        "exchange": "TVC",
    },
]


def normalize_asset_key(value: str) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


TWELVEDATA_SYMBOL_MAP: Dict[str, List[TwelveSymbol]] = {
    "audusd": [("AUD/USD", None)],
    "audusdotc": [("AUD/USD", None)],
    "sp500": [("SPX", None)],
    "spx": [("SPX", None)],
    "us500": [("SPX", None)],
    "dax": [("DAX", None)],
    "ger40": [("DAX", None)],
    "nikkei": [("NI225", None)],
    "nikkei225": [("NI225", None)],
    "ni225": [("NI225", None)],
    "appleotc": [("AAPL", None)],
    "teslaotc": [("TSLA", None)],
    "nvidiaotc": [("NVDA", None)],
    "advancedmicrodevicesotc": [("AMD", None)],
    "alibabaotc": [("BABA", None)],
    "amazonotc": [("AMZN", None)],
    "americanexpressotc": [("AXP", None)],
    "boeingcompanyotc": [("BA", None)],
    "ciscootc": [("CSCO", None)],
    "citigroupincotc": [("C", None)],
    "coinbaseglobalotc": [("COIN", None)],
    "exxonmobilotc": [("XOM", None)],
    "facebookincotc": [("META", None)],
    "fedexotc": [("FDX", None)],
    "gamestopcorpotc": [("GME", None)],
    "intelotc": [("INTC", None)],
    "johnsonjohnsonotc": [("JNJ", None)],
    "marathondigitalholdingsotc": [("MARA", None)],
    "mcdonaldsotc": [("MCD", None)],
    "microsoftotc": [("MSFT", None)],
    "netflixotc": [("NFLX", None)],
    "palantirtechnologiesotc": [("PLTR", None)],
    "pfizerincotc": [("PFE", None)],
    "visaotc": [("V", None)],
    "vixotc": [("VIXY", None)],
    "naturalgas": [("BOIL", None), ("NGSP", "LSE")],
    "naturalgasotc": [("BOIL", None), ("NGSP", "LSE")],
    "ngusd": [("BOIL", None), ("NGSP", "LSE")],
    "gas": [("BOIL", None), ("NGSP", "LSE")],
    "gasotc": [("BOIL", None), ("NGSP", "LSE")],
    "wheat": [("WEAT", None)],
    "wheatotc": [("WEAT", None)],
    "w1": [("WEAT", None)],
    "corn": [("CORN", "NYSE")],
    "cornotc": [("CORN", "NYSE")],
    "c1": [("CORN", "NYSE")],
    "soybeans": [("SOYB", "NYSE")],
    "soybean": [("SOYB", "NYSE")],
    "soybeansotc": [("SOYB", "NYSE")],
    "soybeanotc": [("SOYB", "NYSE")],
    "s1": [("SOYB", "NYSE")],
    "cotton": [("COTN", "LSE")],
    "cottonotc": [("COTN", "LSE")],
    "ct1": [("COTN", "LSE")],
    "sugar": [("SUGA", "LSE")],
    "sugarotc": [("SUGA", "LSE")],
    "sb1": [("SUGA", "LSE")],
    "coffee": [("COFF", "LSE")],
    "coffeeotc": [("COFF", "LSE")],
    "kc1": [("COFF", "LSE")],
    "cocoa": [("CC1", None)],
    "cocoaotc": [("CC1", None)],
    "cc1": [("CC1", None)],
}

for stock_name, stock_symbol in FOREX_STOCK_SYMBOLS:
    for alias in (stock_name, f"{stock_name} OTC", stock_symbol):
        TWELVEDATA_SYMBOL_MAP.setdefault(normalize_asset_key(alias), [(stock_symbol, None)])


def get_twelvedata_symbol_candidates(asset: str) -> List[TwelveSymbol]:
    key = normalize_asset_key(asset)
    candidates = list(TWELVEDATA_SYMBOL_MAP.get(key, []))
    direct = str(asset or "").strip().replace(" OTC", "")
    if direct and "/" in direct:
        candidates.append((direct, None))

    unique: List[TwelveSymbol] = []
    seen = set()
    for symbol, exchange in candidates:
        marker = (str(symbol or "").upper(), str(exchange or "").upper())
        if symbol and marker not in seen:
            seen.add(marker)
            unique.append((symbol, exchange))
    return unique


def has_explicit_twelvedata_mapping(asset: str) -> bool:
    return normalize_asset_key(asset) in TWELVEDATA_SYMBOL_MAP


def get_custom_forex_currency_assets() -> List[Dict[str, str]]:
    return [dict(item) for item in CUSTOM_FOREX_CURRENCY_ASSETS]


def get_custom_forex_index_assets() -> List[Dict[str, str]]:
    return [dict(item) for item in CUSTOM_FOREX_INDEX_ASSETS]


def merge_custom_market_assets(rows: List[Dict[str, Any]], additions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged = [dict(item) for item in rows if isinstance(item, dict)]
    seen = {}
    for index, item in enumerate(merged):
        key_source = item.get("pair") or item.get("symbol") or item.get("asset") or item.get("name") or item.get("label")
        key = normalize_asset_key(key_source)
        if key:
            seen[key] = index
    for item in additions:
        if not isinstance(item, dict):
            continue
        key_source = item.get("pair") or item.get("symbol") or item.get("asset") or item.get("name") or item.get("label")
        key = normalize_asset_key(key_source)
        if not key:
            continue
        if key in seen:
            merged[seen[key]] = {**merged[seen[key]], **dict(item)}
        else:
            seen[key] = len(merged)
            merged.append(dict(item))
    return merged


def get_forex_stock_assets() -> List[Dict[str, str]]:
    return [
        {
            "pair": symbol,
            "asset": symbol,
            "symbol": symbol,
            "name": name,
            "label": name,
            "market": "stocks",
        }
        for name, symbol in FOREX_STOCK_SYMBOLS
    ]
