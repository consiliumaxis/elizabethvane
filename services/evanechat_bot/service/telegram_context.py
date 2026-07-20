def business_connection_kwargs(business_id: str | None) -> dict:
    """Возвращает Business-параметр только для ответа от подключённого аккаунта."""
    return {"business_connection_id": business_id} if business_id else {}
