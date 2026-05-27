import hashlib


POCKET_USER_INFO_ENDPOINT_TEMPLATE = "https://pocketpartners.com/api/user-info/{user_id}/{partner_id}/{hash}"


def mask_secret(value: str) -> str:
    secret = str(value or "").strip()
    if not secret:
        return ""
    if len(secret) <= 4:
        return "*" * len(secret)
    return f"{secret[:2]}{'*' * max(len(secret) - 4, 4)}{secret[-2:]}"


def build_pocket_user_info_url(user_id: str, partner_id: str, api_token: str) -> str:
    trader_id = str(user_id or "").strip()
    cabinet_id = str(partner_id or "").strip()
    token = str(api_token or "").strip()
    signature = hashlib.md5(f"{trader_id}:{cabinet_id}:{token}".encode("utf-8")).hexdigest()
    return f"https://pocketpartners.com/api/user-info/{trader_id}/{cabinet_id}/{signature}"
