import json
import unittest

from backend.staff_permissions import (
    ALL_PERMISSIONS,
    PERM_SETTINGS_API,
    PERM_STAFF_MANAGE,
    PERM_STATS_COMMAND,
    PERM_STATS_MANAGE,
    PERM_STATS_VIEW,
    PERM_USERS_BALANCE,
    PERM_USERS_VIEW,
    has_permission,
    normalize_staff_permissions,
    permissions_are_subset,
    role_default_permissions,
)


class StaffPermissionsTests(unittest.TestCase):
    def test_role_templates_are_safe_and_backward_compatible(self):
        manager = role_default_permissions("manager")
        admin = role_default_permissions("admin")

        self.assertTrue(manager[PERM_STATS_COMMAND])
        self.assertFalse(manager[PERM_USERS_VIEW])
        self.assertTrue(all(admin.values()))
        self.assertEqual(set(admin), set(ALL_PERMISSIONS))

    def test_child_permissions_enable_their_parent_section(self):
        permissions = normalize_staff_permissions(
            {
                PERM_STATS_MANAGE: True,
                PERM_USERS_BALANCE: True,
            },
            "manager",
            use_role_defaults_when_empty=False,
        )

        self.assertTrue(permissions[PERM_STATS_VIEW])
        self.assertTrue(permissions[PERM_USERS_VIEW])

    def test_explicit_json_does_not_restore_role_defaults(self):
        permissions = normalize_staff_permissions(
            json.dumps({PERM_SETTINGS_API: True}),
            "admin",
        )

        self.assertTrue(permissions[PERM_SETTINGS_API])
        self.assertFalse(permissions[PERM_STAFF_MANAGE])

    def test_protected_staff_always_has_every_permission(self):
        profile = {
            "is_protected": True,
            "permissions": {},
        }
        self.assertTrue(has_permission(profile, PERM_STAFF_MANAGE))
        self.assertTrue(has_permission(profile, PERM_SETTINGS_API))

    def test_actor_cannot_grant_permissions_they_do_not_have(self):
        actor = {
            "is_protected": False,
            "permissions": {
                PERM_STAFF_MANAGE: True,
                PERM_STATS_COMMAND: True,
                PERM_SETTINGS_API: False,
            },
        }
        allowed = normalize_staff_permissions(
            {PERM_STATS_COMMAND: True},
            "manager",
            use_role_defaults_when_empty=False,
        )
        elevated = normalize_staff_permissions(
            {PERM_SETTINGS_API: True},
            "manager",
            use_role_defaults_when_empty=False,
        )

        self.assertTrue(permissions_are_subset(allowed, actor))
        self.assertFalse(permissions_are_subset(elevated, actor))


if __name__ == "__main__":
    unittest.main()
