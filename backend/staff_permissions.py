import json
from typing import Any, Dict, Iterable


PERM_STATS_VIEW = "statistics.view"
PERM_STATS_MANAGE = "statistics.manage"
PERM_STATS_COMMAND = "statistics.command"
PERM_DASHBOARD_VIEW = "dashboard.view"
PERM_USERS_VIEW = "users.view"
PERM_USERS_PROFILE_EDIT = "users.profile_edit"
PERM_USERS_ARCHIVE_CLEAR = "users.archive_clear"
PERM_USERS_ACCESS = "users.access"
PERM_USERS_BALANCE = "users.balance"
PERM_USERS_BLOCK = "users.block"
PERM_USERS_DELETE = "users.delete"
PERM_STAFF_VIEW = "staff.view"
PERM_STAFF_ADD = "staff.add"
PERM_STAFF_MANAGE = "staff.manage"
PERM_BROADCAST_MANAGE = "broadcast.manage"
PERM_SETTINGS_STREAMS = "settings.streams"
PERM_SETTINGS_AI = "settings.ai"
PERM_SETTINGS_SYSTEM_ACCESS = "settings.system_access"
PERM_SETTINGS_FUNNEL = "settings.funnel"
PERM_SETTINGS_API = "settings.api"
PERM_SETTINGS_INTERFACE = "settings.interface"
PERM_STRATEGIES_MANAGE = "strategies.manage"
PERM_AICHATTER_MANAGE = "aichatter.manage"

ALL_PERMISSIONS = (
    PERM_STATS_VIEW,
    PERM_STATS_MANAGE,
    PERM_STATS_COMMAND,
    PERM_DASHBOARD_VIEW,
    PERM_USERS_VIEW,
    PERM_USERS_PROFILE_EDIT,
    PERM_USERS_ARCHIVE_CLEAR,
    PERM_USERS_ACCESS,
    PERM_USERS_BALANCE,
    PERM_USERS_BLOCK,
    PERM_USERS_DELETE,
    PERM_STAFF_VIEW,
    PERM_STAFF_ADD,
    PERM_STAFF_MANAGE,
    PERM_BROADCAST_MANAGE,
    PERM_SETTINGS_STREAMS,
    PERM_SETTINGS_AI,
    PERM_SETTINGS_SYSTEM_ACCESS,
    PERM_SETTINGS_FUNNEL,
    PERM_SETTINGS_API,
    PERM_SETTINGS_INTERFACE,
    PERM_STRATEGIES_MANAGE,
    PERM_AICHATTER_MANAGE,
)

ADMIN_CENTER_PERMISSIONS = tuple(
    permission for permission in ALL_PERMISSIONS if permission != PERM_STATS_COMMAND
)

SETTINGS_PERMISSIONS = (
    PERM_SETTINGS_STREAMS,
    PERM_SETTINGS_AI,
    PERM_SETTINGS_SYSTEM_ACCESS,
    PERM_SETTINGS_FUNNEL,
    PERM_SETTINGS_API,
    PERM_SETTINGS_INTERFACE,
)


def role_default_permissions(role: Any) -> Dict[str, bool]:
    normalized_role = str(role or "").strip().lower()
    if normalized_role == "admin":
        return {permission: True for permission in ALL_PERMISSIONS}
    return {
        permission: permission == PERM_STATS_COMMAND
        for permission in ALL_PERMISSIONS
    }


def _decode_permissions(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def normalize_staff_permissions(
    value: Any,
    role: Any = "manager",
    *,
    protected: bool = False,
    use_role_defaults_when_empty: bool = True,
) -> Dict[str, bool]:
    if protected:
        return {permission: True for permission in ALL_PERMISSIONS}

    decoded = _decode_permissions(value)
    if not decoded and use_role_defaults_when_empty:
        normalized = role_default_permissions(role)
    else:
        normalized = {
            permission: bool(decoded.get(permission, False))
            for permission in ALL_PERMISSIONS
        }

    # Child actions are never useful without their parent section.
    if normalized[PERM_STATS_MANAGE]:
        normalized[PERM_STATS_VIEW] = True
    if any(
        normalized[permission]
        for permission in (
            PERM_USERS_PROFILE_EDIT,
            PERM_USERS_ARCHIVE_CLEAR,
            PERM_USERS_ACCESS,
            PERM_USERS_BALANCE,
            PERM_USERS_BLOCK,
            PERM_USERS_DELETE,
        )
    ):
        normalized[PERM_USERS_VIEW] = True
    if normalized[PERM_STAFF_ADD] or normalized[PERM_STAFF_MANAGE]:
        normalized[PERM_STAFF_VIEW] = True
    return normalized


def serialize_staff_permissions(value: Any, role: Any = "manager") -> str:
    return json.dumps(
        normalize_staff_permissions(value, role, use_role_defaults_when_empty=False),
        ensure_ascii=False,
        sort_keys=True,
    )


def has_permission(profile: Dict[str, Any], permission: str) -> bool:
    if permission not in ALL_PERMISSIONS:
        return False
    if bool(profile.get("is_protected")):
        return True
    return bool((profile.get("permissions") or {}).get(permission))


def has_any_permission(profile: Dict[str, Any], permissions: Iterable[str]) -> bool:
    return any(has_permission(profile, permission) for permission in permissions)


def permissions_are_subset(
    requested: Dict[str, bool],
    actor_profile: Dict[str, Any],
) -> bool:
    if bool(actor_profile.get("is_protected")):
        return True
    return all(
        not enabled or has_permission(actor_profile, permission)
        for permission, enabled in requested.items()
    )
