import os
import json
import httpx
import asyncio
import aiomysql

OPENAI_URL = "https://api.openai.com/v1/chat/completions"

async def get_ai_settings(db_pool):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT system_prompt, model FROM ai_settings WHERE id = 1")
            return await cur.fetchone()

async def call_openai(messages, model="gpt-4o-mini"):
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("CRITICAL ERROR: OPENAI_API_KEY is None! Check your .env file.")
        return "Sorry, server configuration error (missing API key)."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 1000,
        "temperature": 0.7
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(OPENAI_URL, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"OpenAI Error: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"OpenAI Response Text: {e.response.text}")
            return "Sorry, I cannot process your request right now. Please try again later."

async def generate_title_task(db_pool, chat_id, user_id, first_messages):
    # Строгий промпт для генерации короткого и красивого названия
    prompt = """Analyze the user's message and generate a very short title for this chat (1 to 3 words maximum). 
    Rules:
    - NEVER use quotes.
    - NEVER use punctuation at the end.
    - Write strictly in the exact same language the user is speaking.
    - Just the essence. Example: Bitcoin Analysis"""
    
    messages = [{"role": "system", "content": prompt}]
    for msg in first_messages:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    title = await call_openai(messages)
    title = title.replace('"', '').replace("'", "").strip()
    
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE ai_chats SET title = %s WHERE id = %s AND user_id = %s", (title, chat_id, user_id))

async def process_user_message(db_pool, user_id: int, chat_id: int, text: str):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # Добавили извлечение title
            await cur.execute("""
                SELECT c.id, c.title, c.message_count, c.context_summary 
                FROM ai_chats c
                WHERE c.id = %s AND c.user_id = %s
            """, (chat_id, user_id))
            chat = await cur.fetchone()
            
            if not chat:
                return {"error": "Chat not found"}

            await cur.execute("INSERT INTO ai_messages (chat_id, role, content) VALUES (%s, 'user', %s)", (chat_id, text))
            new_msg_count = chat['message_count'] + 1
            await cur.execute("UPDATE ai_chats SET message_count = %s, updated_at = NOW() WHERE id = %s", (new_msg_count, chat_id))
            
            # Генерируем название, если это первое сообщение, ИЛИ если название всё ещё дефолтное
            if new_msg_count == 1 or chat['title'] in ['Новый диалог', 'New Chat']:
                # Передаем только текст пользователя для создания названия, чтобы ИИ не запутался
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
    
    if chat['context_summary']:
        messages_payload.append({"role": "system", "content": f"Summary of previous context: {chat['context_summary']}"})
        
    for msg in recent_messages:
        messages_payload.append({"role": msg['role'], "content": msg['content']})

    ai_response = await call_openai(messages_payload, model=settings['model'])

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("INSERT INTO ai_messages (chat_id, role, content) VALUES (%s, 'assistant', %s)", (chat_id, ai_response))
            await cur.execute("UPDATE ai_chats SET message_count = message_count + 1 WHERE id = %s", (chat_id,))

    return {"status": "success", "response": ai_response}