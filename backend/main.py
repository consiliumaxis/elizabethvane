import os
import asyncio
import aiomysql
import httpx
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from dotenv import load_dotenv
import uvicorn
import ai_service
from pydantic import BaseModel
from typing import Optional
from analysis_engine import compute_analysis_decision

load_dotenv()

def get_env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        print(f"[Config] Invalid {name}={raw!r}, fallback to {default}")
        return default
    if not (1 <= value <= 65535):
        print(f"[Config] {name} out of range ({value}), fallback to {default}")
        return default
    return value

API_HOST = (os.getenv("API_HOST") or "0.0.0.0").strip() or "0.0.0.0"
API_PORT = get_env_int("API_PORT", 8000)

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "db": os.getenv("DB_NAME"),
    "autocommit": True
}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db_pool = None
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

analysis_queue = asyncio.Queue()
processing_ids = set() 
price_cache = {} 

COMMODITY_SYMBOLS = ["HG1", "W_1", "C_1", "S_1", "KC1", "CC1", "SB1", "CT1"]

@app.get("/api/support/links")
async def get_support_links():
    channel_url = (os.getenv("CHANNEL_URL") or "").strip()
    support_url = (os.getenv("SUPPORT_URL") or "").strip()
    return {
        "channel_url": channel_url,
        "support_url": support_url
    }

def parse_timeframe_mins(tf: str) -> int:
    if not tf: return 5
    tf = tf.lower()
    try:
        if tf.endswith('m'): return int(tf[:-1])
        if tf.endswith('min'): return int(tf[:-3])
        if tf.endswith('h'): return int(tf[:-1]) * 60
        if tf.endswith('hour'): return int(tf[:-4]) * 60
        if tf.endswith('d'): return int(tf[:-1]) * 1440
        if tf.endswith('day'): return int(tf[:-3]) * 1440
    except:
        pass
    return 5

async def get_price_for_symbol(client: httpx.AsyncClient, symbol: str, token: str) -> Optional[float]:
    clean_sym = symbol.replace("/", "").replace("-", "").strip().upper()
    now = asyncio.get_event_loop().time()
    
    if clean_sym in price_cache and price_cache[clean_sym]["expires"] > now:
        return price_cache[clean_sym]["price"]
        
    url = f"https://api.devsbite.com/price/{clean_sym}"
    headers = {
        "accept": "application/json",
        "X-Client-Token": token
    }
    
    try:
        resp = await client.get(url, headers=headers, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            price = data.get("price")
            if price is not None:
                price = float(price)
                price_cache[clean_sym] = {"price": price, "expires": now + 30}
                return price
    except Exception as e:
        print(f"[Worker] Failed to fetch price for {clean_sym} via proxy: {e}")
        
    if clean_sym in COMMODITY_SYMBOLS:
        td_key = os.getenv("TD_API_KEY")
        if td_key:
            try:
                td_url = f"https://api.twelvedata.com/price?symbol={clean_sym}:COMMODITY&apikey={td_key}"
                resp = await client.get(td_url, timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    price = data.get("price") or data.get("close")
                    if price is not None:
                        price = float(price)
                        price_cache[clean_sym] = {"price": price, "expires": now + 30}
                        return price
            except Exception as e:
                print(f"[Worker] Failed to fetch TD price for {clean_sym}: {e}")

    return None

async def analysis_producer():
    print("[Worker] Producer started...")
    while True:
        try:
            if db_pool:
                async with db_pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cur:
                        await cur.execute("""
                            SELECT id, pair, timeframe, created_at, raw_data 
                            FROM user_analyses 
                            WHERE status = 'active' AND created_at < NOW() - INTERVAL 5 MINUTE
                        """)
                        rows = await cur.fetchall()

                now = datetime.now()
                for row in rows:
                    a_id = row['id']
                    if a_id in processing_ids:
                        continue

                    created_at = row['created_at']
                    if isinstance(created_at, str):
                        try:
                            created_at = datetime.fromisoformat(created_at.replace('Z', ''))
                        except:
                            continue

                    tf_mins = parse_timeframe_mins(row['timeframe'])
                    expiration_time = created_at + timedelta(minutes=tf_mins + 10)

                    if now >= expiration_time:
                        processing_ids.add(a_id)
                        await analysis_queue.put(row)

        except Exception as e:
            print(f"[Worker] Producer error: {e}")
            
        await asyncio.sleep(30)

async def analysis_consumer():
    print("[Worker] Consumer started...")
    token = os.getenv("DEVSBITE_TOKEN")
    
    async with httpx.AsyncClient() as client:
        while True:
            try:
                item = await analysis_queue.get()
                items_to_process = [item]
                
                while not analysis_queue.empty():
                    try:
                        items_to_process.append(analysis_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                        
                async with db_pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        for row in items_to_process:
                            a_id = row['id']
                            symbol = row['pair']
                            raw_data = row['raw_data']
                            
                            try:
                                raw = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                                orig_price = float(raw.get('price', 0))
                                rec = raw.get('recommendation')
                            except:
                                orig_price, rec = 0, None
                                
                            new_status = 'skipped'
                            
                            if orig_price > 0 and rec in ['BUY', 'SELL']:
                                current_price = await get_price_for_symbol(client, symbol, token)
                                
                                if current_price is not None:
                                    if rec == 'BUY':
                                        if current_price > orig_price: new_status = 'success'
                                        elif current_price < orig_price: new_status = 'fail'
                                    elif rec == 'SELL':
                                        if current_price < orig_price: new_status = 'success'
                                        elif current_price > orig_price: new_status = 'fail'
                            
                            await cur.execute("UPDATE user_analyses SET status = %s WHERE id = %s", (new_status, a_id))
                            
                            processing_ids.discard(a_id)
                            analysis_queue.task_done()
                            
            except Exception as e:
                print(f"[Worker] Consumer error: {e}")
                await asyncio.sleep(5)



@app.post("/api/user/profile")
async def get_profile(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT u.user_id, u.lang, u.mode, u.username, u.first_name, u.avatar_url, 
                       u.strategy_id, p.name as strategy_name
                FROM users u
                LEFT JOIN presets p ON u.strategy_id = p.id
                WHERE u.user_id = %s
            """, (user_id,))
            user = await cur.fetchone()
    return user or {"error": "Not found"}

@app.get("/api/indicators")
async def get_indicators():
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, name, `key` FROM indicators")
            indicators = await cur.fetchall()
    return {"indicators": indicators}

@app.get("/api/strategies")
async def get_strategies(user_id: int):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT p.id, p.name, p.is_system, p.icon, p.allowed_timeframes,
                       GROUP_CONCAT(i.name SEPARATOR ', ') as indicators_list,
                       GROUP_CONCAT(i.id SEPARATOR ',') as indicator_ids,
                       GROUP_CONCAT(i.key SEPARATOR ',') as indicator_keys
                FROM presets p
                LEFT JOIN preset_indicators pi ON p.id = pi.preset_id
                LEFT JOIN indicators i ON pi.indicator_id = i.id
                LEFT JOIN user_presets up ON p.id = up.preset_id
                WHERE p.is_system = 1 OR up.user_id = %s
                GROUP BY p.id
            """, (user_id,))
            strategies = await cur.fetchall()
    return {"strategies": strategies}

@app.post("/api/user/strategy")
async def update_strategy(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    strategy_id = data.get("strategy_id")
    
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE users SET strategy_id = %s WHERE user_id = %s", (strategy_id, user_id))
    return {"status": "success", "strategy_id": strategy_id}

@app.post("/api/user/strategy/manage")
async def manage_custom_strategy(request: Request):
    data = await request.json()
    action = data.get("action") 
    user_id = data.get("user_id")
    
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            if action == "create":
                name = data.get("name")
                icon = data.get("icon", "\u26A1")
                indicators = data.get("indicators", [])
                
                await cur.execute("INSERT INTO presets (name, is_system, icon) VALUES (%s, 0, %s)", (name, icon))
                preset_id = cur.lastrowid
                
                await cur.execute("INSERT INTO user_presets (user_id, preset_id) VALUES (%s, %s)", (user_id, preset_id))
                
                for ind_id in indicators:
                    await cur.execute("INSERT INTO preset_indicators (preset_id, indicator_id) VALUES (%s, %s)", (preset_id, ind_id))
                
                await cur.execute("UPDATE users SET strategy_id = %s WHERE user_id = %s", (preset_id, user_id))
                return {"status": "success", "strategy_id": preset_id}

            elif action == "update":
                preset_id = data.get("preset_id")
                name = data.get("name")
                icon = data.get("icon", "\u26A1")
                indicators = data.get("indicators", [])
                
                await cur.execute("UPDATE presets SET name = %s, icon = %s WHERE id = %s AND is_system = 0", (name, icon, preset_id))
                
                await cur.execute("DELETE FROM preset_indicators WHERE preset_id = %s", (preset_id,))
                for ind_id in indicators:
                    await cur.execute("INSERT INTO preset_indicators (preset_id, indicator_id) VALUES (%s, %s)", (preset_id, ind_id))
                return {"status": "success"}

            elif action == "delete":
                preset_id = data.get("preset_id")
                await cur.execute("DELETE FROM preset_indicators WHERE preset_id = %s", (preset_id,))
                await cur.execute("DELETE FROM user_presets WHERE preset_id = %s AND user_id = %s", (preset_id, user_id))
                await cur.execute("DELETE FROM presets WHERE id = %s AND is_system = 0", (preset_id,))
                
                await cur.execute("""
                    UPDATE users 
                    SET strategy_id = 1 
                    WHERE user_id = %s AND strategy_id = %s
                """, (user_id, preset_id))
                return {"status": "success"}

    return {"error": "Invalid action"}

@app.post("/api/user/sync")
async def sync_user(request: Request):
    data = await request.json()
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO users (user_id, username, first_name, avatar_url, lang, mode)
                VALUES (%s, %s, %s, %s, 'ru', 'forex')
                ON DUPLICATE KEY UPDATE 
                    username = VALUES(username),
                    first_name = VALUES(first_name),
                    avatar_url = VALUES(avatar_url)
            """, (data["user_id"], data["username"], data["first_name"], data.get("avatar_url")))
    return {"status": "success"}
    
@app.post("/api/user/mode")
async def update_mode(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    new_mode = data.get("mode")
    
    if user_id and new_mode:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE users SET mode = %s WHERE user_id = %s", (new_mode, user_id))
        return {"status": "success", "mode": new_mode}
    return {"error": "Invalid data"}

@app.get("/api/pairs/forex")
async def get_forex_pairs():
    token = os.getenv("DEVSBITE_TOKEN")
    url = "https://api.devsbite.com/pairs/forex?min_payout=34"
    headers = {
        "accept": "application/json",
        "X-Client-Token": token
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            if "pairs" in data:
                data["pairs"] = sorted(data["pairs"], key=lambda x: x["payout"], reverse=True)
            return data
        except Exception as e:
            return {"error": str(e), "pairs": []}
            
@app.get("/api/pairs/commodity")
async def get_commodity_pairs():
    token = os.getenv("DEVSBITE_TOKEN")
    url = "https://api.devsbite.com/pairs/commodity"
    headers = {
        "accept": "application/json",
        "X-Client-Token": token
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Commodity API Error: {e}")
            return [] 

@app.get("/api/pairs/indices")
async def get_indices_pairs():
    token = os.getenv("DEVSBITE_TOKEN")
    url = "https://api.devsbite.com/pairs/indices"
    headers = {
        "accept": "application/json",
        "X-Client-Token": token
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Indices API Error: {e}")
            return []
            
@app.get("/api/analysis/active")
async def get_active_analyses(user_id: int):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT a.id, a.pair, a.timeframe, a.strategy_id, a.raw_data, a.news_data, a.created_at, p.name as strategy_name
                FROM user_analyses a
                LEFT JOIN presets p ON a.strategy_id = p.id
                WHERE a.user_id = %s AND a.status = 'active'
                ORDER BY a.created_at DESC
            """, (user_id,))
            analyses = await cur.fetchall()
            
            for a in analyses:
                if isinstance(a['raw_data'], str):
                    a['raw_data'] = json.loads(a['raw_data'])
                if a.get('news_data') and isinstance(a['news_data'], str):
                    a['news_data'] = json.loads(a['news_data'])
                    
    return {"analyses": analyses}

@app.get("/api/analysis/history")
async def get_analysis_history(user_id: int):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT a.id, a.pair, a.timeframe, a.status, a.created_at, p.name as strategy_name 
                FROM user_analyses a
                LEFT JOIN presets p ON a.strategy_id = p.id
                WHERE a.user_id = %s AND a.status != 'active'
                ORDER BY a.created_at DESC
            """, (user_id,))
            history = await cur.fetchall()

    success_count = sum(1 for item in history if item['status'] == 'success')
    fail_count = sum(1 for item in history if item['status'] == 'fail')
    skipped_count = sum(1 for item in history if item['status'] == 'skipped')

    return {
        "history": history,
        "stats": {
            "success": success_count,
            "fail": fail_count,
            "skipped": skipped_count,
            "total": len(history)
        }
    }

@app.get("/api/news")
async def get_news():
    token = os.getenv("FINNHUB_TOKEN")
    url = f"https://finnhub.io/api/v1/calendar/economic?token={token}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5.0)
            if response.status_code != 200:
                return {"economicCalendar": []}
            raw_data = response.json()
    except Exception as e:
        print(f"News API Error: {e}")
        return {"economicCalendar": []}

    events = raw_data.get("economicCalendar", [])
    if not events:
        return {"economicCalendar": []}

    country_to_currency = {
        "US": "USD", "GB": "GBP", "CA": "CAD", "AU": "AUD", "NZ": "NZD",
        "JP": "JPY", "CH": "CHF", "CN": "CNY", "RU": "RUB", "TR": "TRY",
        "ZA": "ZAR", "MX": "MXN", "BR": "BRL", "IN": "INR", "KR": "KRW",
        "EU": "EUR", "DE": "EUR", "FR": "EUR", "IT": "EUR", "ES": "EUR"
    }

    symbol_to_currency_map = {
        "XAU": "USD", "XAG": "USD", "XPT": "USD", "XPD": "USD",
        "WTI": "USD", "BRENT": "USD", "XBR": "USD", "NG": "USD"
    }

    now = datetime.utcnow()
    filtered_events = []

    for event in events:
        try:
            event_time = datetime.strptime(event["time"], "%Y-%m-%d %H:%M:%S")
            
            if event_time.date() == now.date() and event_time > (now - timedelta(hours=2)):
                country = event.get("country", "").strip().upper()
                currency = country_to_currency.get(country, "ALL")
                
                event["currency"] = currency
                filtered_events.append(event)
        except:
            continue

    return {"economicCalendar": filtered_events}
    
@app.post("/api/analysis/forex")
async def create_forex_analysis(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    pair = data.get("pair")
    interval_raw = data.get("exp")
    strategy_id = data.get("strategy_id")
    allowed_indicators = data.get("allowed_indicators", [])
    exchange = data.get("exchange")

    interval_map = {
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "1h",
        "4h": "4h",
        "1d": "1day",
    }
    interval = interval_map.get(interval_raw, "5min")

    demo_symbol_map = {
        "SPX": "SPX",
        "NDX": "NDX",
        "DJI": "DJI",
        "DAX": "GDAXI",
        "UK100": "FTSE",
        "NI225": "N225",
    }
    formatted_pair = demo_symbol_map.get(pair)
    if not formatted_pair:
        compact = (pair or "").upper().replace("/", "").replace(" ", "")
        if len(compact) == 6 and compact.isalpha():
            formatted_pair = f"{compact[:3]}/{compact[3:]}"
        else:
            formatted_pair = (pair or "").strip()

    token = os.getenv("DEVSBITE_TOKEN")
    url = (os.getenv("ANALYSIS_GATEWAY_URL") or "https://api.devsbite.com/analysis/advanced").strip()
    headers = {"accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["X-Client-Token"] = token

    payload = {
        "symbol": formatted_pair,
        "interval": interval,
        "allowed_indicators": allowed_indicators,
        "exchange": exchange,
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json=payload, timeout=20.0)
            resp.raise_for_status()
            upstream_data = resp.json()

            analysis_data = compute_analysis_decision(
                upstream_data,
                symbol=formatted_pair,
                interval=interval,
                allowed_indicators=allowed_indicators,
            )
            news_data = await get_news()
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            print(f"ANALYSIS GATEWAY ERROR [{e.response.status_code}]: {error_text} (Payload: {payload})")
            return {"error": f"API Error: {error_text}"}
        except ValueError as e:
            return {"error": f"Analysis parse error: {str(e)}"}
        except Exception as e:
            return {"error": str(e)}

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO user_analyses (user_id, pair, timeframe, strategy_id, raw_data, news_data, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'active')
                """,
                (user_id, pair, interval_raw, strategy_id, json.dumps(analysis_data), json.dumps(news_data)),
            )
            analysis_id = cur.lastrowid

    return {"status": "success", "analysis_id": analysis_id, "data": analysis_data, "news_data": news_data}
@app.post("/api/analysis/status")
async def update_analysis_status(request: Request):
    data = await request.json()
    analysis_id = data.get("analysis_id")
    status = data.get("status") 
    user_id = data.get("user_id")

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                UPDATE user_analyses 
                SET status = %s 
                WHERE id = %s AND user_id = %s
            """, (status, analysis_id, user_id))
    return {"status": "success"}
    
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_name = message.from_user.first_name or message.from_user.username or "Trader"
    
    welcome_text = (
        f"Welcome, {user_name}!\n\n"
        f"<b>Elizabeth Vane</b> | <code>Private Trading Analytics</code>\n\n"
        f"A professional analytical space for those who value precision. "
        f"We've combined advanced technical analysis methods with the convenience of a Web App.\n\n"
        f"<i>Your market edge begins here.</i>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Open Elizabeth Vane",
                web_app=WebAppInfo(url=os.getenv("WEB_APP_URL"))
            )
        ]
    ])
    
    photo_path = "media/menu.jpg"
    photo = FSInputFile(photo_path)
    
    await message.answer_photo(
        photo=photo,
        caption=welcome_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

class AIChatRequest(BaseModel):
    user_id: int
    text: Optional[str] = None
    chat_id: Optional[int] = None

@app.post("/api/ai/chat/active")
async def get_or_create_active_chat(request: AIChatRequest):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT id, title, message_count 
                FROM ai_chats 
                WHERE user_id = %s AND status = 'active' 
                AND updated_at >= NOW() - INTERVAL 24 HOUR
                ORDER BY updated_at DESC LIMIT 1
            """, (request.user_id,))
            chat = await cur.fetchone()

            if not chat:
                await cur.execute("UPDATE ai_chats SET status = 'archived' WHERE user_id = %s AND status = 'active'", (request.user_id,))
                await cur.execute("INSERT INTO ai_chats (user_id) VALUES (%s)", (request.user_id,))
                chat_id = cur.lastrowid
                return {"status": "success", "chat_id": chat_id, "title": "New Chat", "messages": []}

            await cur.execute("SELECT id, role, content, created_at as timestamp FROM ai_messages WHERE chat_id = %s ORDER BY id ASC", (chat['id'],))
            messages = await cur.fetchall()
            
            return {"status": "success", "chat_id": chat['id'], "title": chat['title'], "messages": messages}

@app.post("/api/ai/chat/send")
async def send_chat_message(request: AIChatRequest):
    if not request.text or not request.chat_id:
        return {"error": "text and chat_id are required"}
    result = await ai_service.process_user_message(db_pool, request.user_id, request.chat_id, request.text)
    return result

@app.post("/api/ai/chat/history")
async def get_chat_history(request: AIChatRequest):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT id, title, status, updated_at 
                FROM ai_chats 
                WHERE user_id = %s 
                ORDER BY updated_at DESC 
                LIMIT 10
            """, (request.user_id,))
            chats = await cur.fetchall()
    return {"status": "success", "chats": chats}

@app.post("/api/ai/chat/load")
async def load_historical_chat(request: AIChatRequest):
    if not request.chat_id:
        return {"error": "chat_id is required"}
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE ai_chats SET status = 'archived' WHERE user_id = %s AND status = 'active'", (request.user_id,))
            await cur.execute("UPDATE ai_chats SET status = 'active', updated_at = NOW() WHERE id = %s AND user_id = %s", (request.chat_id, request.user_id))
    return await get_or_create_active_chat(request)

@app.post("/api/ai/chat/new")
async def create_new_chat(request: AIChatRequest):
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE ai_chats SET status = 'archived' WHERE user_id = %s AND status = 'active'", (request.user_id,))
            await cur.execute("INSERT INTO ai_chats (user_id) VALUES (%s)", (request.user_id,))
            chat_id = cur.lastrowid
    return {"status": "success", "chat_id": chat_id, "title": "New Chat", "messages": []}
    
async def start_bot():
    await dp.start_polling(bot)

async def start_api():
    config = uvicorn.Config(app, host=API_HOST, port=API_PORT)
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    global db_pool
    db_pool = await aiomysql.create_pool(**DB_CONFIG)
    
    await asyncio.gather(
        start_bot(), 
        start_api(),
        analysis_producer(),
        analysis_consumer()
    )

if __name__ == "__main__":
    async def main_wrapper():
        try:
            await main()
        except KeyboardInterrupt:
            pass
    asyncio.run(main_wrapper())
