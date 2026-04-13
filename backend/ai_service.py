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
    }
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT system_prompt, model FROM ai_settings WHERE id = 1")
                row = await cur.fetchone()
                if not row:
                    return default_settings
                return {
                    "system_prompt": row.get("system_prompt") or default_settings["system_prompt"],
                    "model": row.get("model") or default_settings["model"],
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


async def call_openai(messages, model="gpt-4o-mini") -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        err = "OPENAI_API_KEY is not configured"
        print(f"CRITICAL ERROR: {err}")
        return {"ok": False, "error": err}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
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

async def generate_title_task(db_pool, chat_id, user_id, first_messages):
    prompt = """Analyze the user's message and generate a very short title for this chat (1 to 3 words maximum). 
    Rules:
    - NEVER use quotes.
    - NEVER use punctuation at the end.
    - Write strictly in the exact same language the user is speaking.
    - Just the essence. Example: Bitcoin Analysis"""
    
    messages = [{"role": "system", "content": prompt}]
    for msg in first_messages:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    result = await call_openai(messages)
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
    
    system_prompt = f"{settings['system_prompt']} IMPORTANT: Always reply in the EXACT SAME LANGUAGE that the user used in their message."
    
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

    ai_result = await call_openai(messages_payload, model=settings['model'])
    if not ai_result.get("ok"):
        return {"status": "error", "error": ai_result.get("error") or "AI provider request failed"}
    ai_response = ai_result.get("text") or ""

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("INSERT INTO ai_messages (chat_id, role, content) VALUES (%s, 'assistant', %s)", (chat_id, ai_response))
            await cur.execute("UPDATE ai_chats SET updated_at = NOW() WHERE id = %s", (chat_id,))

    return {"status": "success", "response": ai_response}
