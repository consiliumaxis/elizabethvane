import os
import json
import httpx
import asyncio
import aiomysql
from typing import Any, Dict, List

OPENAI_URL = "https://api.openai.com/v1/chat/completions"

async def get_ai_settings(db_pool):
    default_settings = {
        "system_prompt": "You are a helpful trading assistant.",
        "model": "gpt-4o-mini",
        "api_key": "",
    }
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT system_prompt, model FROM ai_settings WHERE id = 1")
                row = await cur.fetchone() or {}
                await cur.execute("SELECT gpt_api_key FROM admin_analysis_settings WHERE id = 1 LIMIT 1")
                admin_row = await cur.fetchone() or {}
                return {
                    "system_prompt": row.get("system_prompt") or default_settings["system_prompt"],
                    "model": row.get("model") or default_settings["model"],
                    "api_key": str(admin_row.get("gpt_api_key") or "").strip(),
                }
    except Exception as e:
        print(f"AI settings fallback due to DB error: {e}")
        return default_settings

def _extract_error_text(response: httpx.Response) -> str:
    try:
        data = response.json()
    except Exception:
        return (response.text or "").strip()[:500]
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            msg = err.get("message") or ""
            code = err.get("code") or ""
            typ = err.get("type") or ""
            parts = [str(x) for x in [msg, code, typ] if x]
            return " | ".join(parts)[:500]
    return str(data)[:500]


def _build_model_candidates(model: str) -> List[str]:
    primary = (model or "").strip() or "gpt-4o-mini"
    env_fallback = (os.getenv("OPENAI_FALLBACK_MODEL") or "").strip()
    candidates: List[str] = [primary]
    if env_fallback:
        candidates.append(env_fallback)
    candidates.extend(["gpt-4o-mini", "gpt-4.1-mini"])
    unique: List[str] = []
    for m in candidates:
        if m and m not in unique:
            unique.append(m)
    return unique


async def call_openai(messages, model="gpt-4o-mini", api_key: str = "") -> Dict[str, Any]:
    selected_key = (api_key or "").strip() or (os.getenv("OPENAI_API_KEY") or "").strip()

    if not selected_key:
        err = "OpenAI API key is not configured"
        print(f"CRITICAL ERROR: {err}")
        return {"ok": False, "error": err}

    timeout = float((os.getenv("OPENAI_TIMEOUT_SEC") or "30").strip())
    url = (os.getenv("OPENAI_URL") or OPENAI_URL).strip() or OPENAI_URL
    last_error = "Unknown OpenAI error"

    async with httpx.AsyncClient() as client:
        for candidate in _build_model_candidates(model):
            payload = {
                "model": candidate,
                "messages": messages,
                "max_tokens": 1000,
                "temperature": 0.7
            }
            headers = {
                "Authorization": f"Bearer {selected_key}",
                "Content-Type": "application/json"
            }
            try:
                response = await client.post(url, headers=headers, json=payload, timeout=timeout)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if isinstance(content, str) and content.strip():
                    return {"ok": True, "text": content, "model": candidate}
                last_error = f"Empty model response for model={candidate}"
            except httpx.HTTPStatusError as e:
                detail = _extract_error_text(e.response)
                last_error = f"HTTP {e.response.status_code} on model={candidate}: {detail}"
                print(f"OpenAI Error: {last_error}")
                if e.response.status_code in (401, 403):
                    break
            except Exception as e:
                last_error = f"{type(e).__name__} on model={candidate}: {str(e)}"
                print(f"OpenAI Error: {last_error}")

    return {"ok": False, "error": last_error}


def _get_project_name() -> str:
    configured = (os.getenv("PROJECT_NAME") or os.getenv("APP_NAME") or "").strip()
    if configured:
        return configured
    cwd_name = os.path.basename(os.getcwd()).lower()
    if "eric" in cwd_name:
        return "Eric Cole"
    if "elizabeth" in cwd_name or "vane" in cwd_name:
        return "Elizabeth Vane"
    return "the analytics app"


def _compact_join(items: List[str], limit: int = 12) -> str:
    clean = [str(item or "").strip() for item in items if str(item or "").strip()]
    if not clean:
        return "none listed"
    if len(clean) <= limit:
        return ", ".join(clean)
    return ", ".join(clean[:limit]) + f", and {len(clean) - limit} more"


async def get_app_knowledge(db_pool) -> str:
    project_name = _get_project_name()
    default_context = f"""
Application context:
- Product: {project_name}, a Telegram WebApp for educational trading analytics.
- Main sections: Profile, Forex analysis, Binary signals, Analysis log, AI chat, FAQ, and Admin Center for administrators.
- The app uses Telegram WebApp authorization, user modes, strategy selection, technical indicators, market news checks, and analysis history.
- It is an educational analytics tool, not financial advice. Never promise profits or guaranteed outcomes.
""".strip()
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT name, `key` FROM indicators ORDER BY name ASC")
                indicators = await cur.fetchall()
                await cur.execute(
                    """
                    SELECT
                        p.id,
                        p.name,
                        p.icon,
                        p.is_system,
                        p.allowed_timeframes,
                        p.public_winrate,
                        GROUP_CONCAT(i.name ORDER BY i.name SEPARATOR ', ') AS indicators_list
                    FROM presets p
                    LEFT JOIN preset_indicators pi ON pi.preset_id = p.id
                    LEFT JOIN indicators i ON i.id = pi.indicator_id
                    GROUP BY p.id
                    ORDER BY p.is_system DESC, p.id ASC
                    LIMIT 30
                    """
                )
                strategies = await cur.fetchall()
    except Exception as e:
        print(f"AI app context fallback due to DB error: {e}")
        return default_context

    indicator_lines = []
    for item in indicators[:40]:
        name = str(item.get("name") or "").strip()
        key = str(item.get("key") or "").strip()
        if name and key:
            indicator_lines.append(f"{name} ({key})")
        elif name:
            indicator_lines.append(name)

    system_strategy_lines = []
    custom_strategy_lines = []
    for row in strategies:
        name = str(row.get("name") or "Unnamed strategy").strip()
        icon = str(row.get("icon") or "").strip()
        timeframes = str(row.get("allowed_timeframes") or "").strip() or "default timeframes"
        indicators_list = str(row.get("indicators_list") or "").strip() or "no indicators listed"
        public_winrate = row.get("public_winrate")
        winrate_part = ""
        if public_winrate is not None:
            try:
                winrate_part = f", displayed winrate {float(public_winrate):.1f}%"
            except (TypeError, ValueError):
                winrate_part = ""
        line = f"{icon + ' ' if icon else ''}{name}: timeframes {timeframes}; indicators: {indicators_list}{winrate_part}"
        if int(row.get("is_system") or 0) == 1:
            system_strategy_lines.append(line)
        else:
            custom_strategy_lines.append(line)

    return f"""
Application context:
- Product: {project_name}, a Telegram WebApp for educational trading analytics.
- Main sections: Profile, Forex analysis, Binary signals, Analysis log, AI chat, FAQ, and Admin Center for administrators.
- Profile: users can choose mode, choose a system strategy, view strategy indicators and displayed winrate, and manage custom strategies where available.
- Forex analysis: users select a pair, timeframe, and strategy; the app returns indicator readings, consensus, key levels, news background, and a recommendation.
- Binary signals: users select a market, pair, expiration, and strategy; the app shows a signal card, countdown, indicators, consensus, and later closes the signal as success, failed, or skipped.
- Analysis log: users can filter historical results by strategy and see success/failure stats and winrate.
- Admin Center: admins manage stats, users, broadcasts, settings, strategies, stream fallback settings, and AI/chat settings.
- Available indicators: {_compact_join(indicator_lines, 40)}.
- System strategies: {_compact_join(system_strategy_lines, 20)}.
- Custom/user strategies may also exist: {_compact_join(custom_strategy_lines, 10)}.
- Safety: this is an educational analytics tool, not financial advice. Never promise profits, certainty, or guaranteed outcomes.
""".strip()

async def generate_title_task(db_pool, chat_id, user_id, first_messages):
    prompt = """Analyze the user's message and generate a very short English title for this chat (1 to 3 words maximum).
    Rules:
    - Always write in English.
    - NEVER use quotes.
    - NEVER use punctuation at the end.
    - Just the essence. Example: Bitcoin Analysis"""
    
    messages = [{"role": "system", "content": prompt}]
    for msg in first_messages:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    settings = await get_ai_settings(db_pool)
    result = await call_openai(messages, model=settings["model"], api_key=settings.get("api_key") or "")
    if not result.get("ok"):
        return
    title = str(result.get("text") or "").replace('"', '').replace("'", "").strip()
    if not title:
        return
    
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE ai_chats SET title = %s WHERE id = %s AND user_id = %s", (title, chat_id, user_id))

async def process_user_message(db_pool, user_id: int, chat_id: int, text: str):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT c.id, c.title
                FROM ai_chats c
                WHERE c.id = %s AND c.user_id = %s
            """, (chat_id, user_id))
            chat = await cur.fetchone()
            
            if not chat:
                return {"error": "Chat not found"}

            await cur.execute("INSERT INTO ai_messages (chat_id, role, content) VALUES (%s, 'user', %s)", (chat_id, text))
            await cur.execute("UPDATE ai_chats SET updated_at = NOW() WHERE id = %s", (chat_id,))
            
            if (chat.get('title') or '').strip() in ['', 'New Chat']:
                asyncio.create_task(generate_title_task(db_pool, chat_id, user_id, [{"role": "user", "content": text}]))

    settings = await get_ai_settings(db_pool)
    app_context = await get_app_knowledge(db_pool)

    system_prompt = f"""{settings['system_prompt']}

{app_context}

Response rules:
- Always answer in English only, even if the user writes in another language.
- Be helpful and practical about how to use the app: strategies, indicators, signals, analysis history, profile settings, FAQ, and admin features.
- If the user asks where something is, give clear navigation steps inside the app.
- When discussing trading, keep it educational and risk-aware. Do not promise profit or certainty.
- If live account, payment, server, or private user data is needed and you cannot see it, say what the user should check in the app instead of inventing facts.
""".strip()

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT role, content FROM (
                    SELECT role, content, id FROM ai_messages WHERE chat_id = %s ORDER BY id DESC LIMIT 12
                ) sub ORDER BY id ASC
            """, (chat_id,))
            recent_messages = await cur.fetchall()

    messages_payload = [{"role": "system", "content": system_prompt}]
    
    for msg in recent_messages:
        messages_payload.append({"role": msg['role'], "content": msg['content']})

    ai_result = await call_openai(messages_payload, model=settings['model'], api_key=settings.get('api_key') or '')
    if not ai_result.get("ok"):
        return {"status": "error", "error": ai_result.get("error") or "AI provider request failed"}
    ai_response = ai_result.get("text") or ""

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("INSERT INTO ai_messages (chat_id, role, content) VALUES (%s, 'assistant', %s)", (chat_id, ai_response))
            await cur.execute("UPDATE ai_chats SET updated_at = NOW() WHERE id = %s", (chat_id,))

    return {"status": "success", "response": ai_response}
