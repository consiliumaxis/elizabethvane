# Eric Cole Parity Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring Elizabeth Vane to feature parity with the current Eric Cole implementation while preserving Elizabeth-specific branding and runtime configuration.

**Architecture:** Treat Eric Cole as the reference implementation and port feature areas into Elizabeth, not entire directories. Backend schema changes stay additive and idempotent; frontend changes reuse Elizabeth components and copy only behavior that is missing or older.

**Tech Stack:** Python FastAPI/aiogram/aiomysql backend, React/Vite frontend, MySQL schema bootstrap, unittest source/regression tests, git branches `main` and `test`.

---

## File Structure

Reference repository:

- `C:/Users/Asus/Desktop/Гитхабелизбает/Ericcole/backend/main.py` - source for the newest backend behavior.
- `C:/Users/Asus/Desktop/Гитхабелизбает/Ericcole/backend/db_bootstrap.py` - source for additive schema migrations.
- `C:/Users/Asus/Desktop/Гитхабелизбает/Ericcole/backend/*_tracking.py`, `backend/*pocket*.py`, `backend/access_policy.py` - source for helper behavior where present.
- `C:/Users/Asus/Desktop/Гитхабелизбает/Ericcole/frontend/src` - source for UI behavior.
- `C:/Users/Asus/Desktop/Гитхабелизбает/Ericcole/backend/tests` - source for regression tests.

Elizabeth target files:

- `backend/main.py` - port admin auth, profile payloads, Pocket/AIO/Chatterfy handlers, access logic, signal normalization.
- `backend/db_bootstrap.py` - add missing columns/tables idempotently.
- `backend/access_policy.py` - create or update if Eric has a helper module that Elizabeth lacks.
- `backend/aio_tracking.py` - create or update URL builders and delivery helpers.
- `backend/chatterfy_tracking.py` - create or update Chatterfy postback delivery helpers.
- `backend/chatterfy_pocket.py` - create or update Pocket-to-Chatterfy helpers.
- `backend/tests/*.py` - add focused regression tests for each migrated feature area.
- `frontend/src/components/pages/Profile.jsx` and `Profile.css` - Telegram avatars and admin entry.
- `frontend/src/admin/pages/UsersPage.jsx` and `frontend/src/admin/admin.css` - user avatars and migrated fields.
- `frontend/src/admin/pages/SettingsPage.jsx` - access policy settings and integration settings.
- `frontend/src/components/binary/BinarySignalSettings.jsx` - binary news block and configured indicator display.
- `frontend/src/components/forex/ForexAnalysisSettings.jsx` - configured indicator display parity and news block checks.
- `frontend/src/locales/texts.js` - Elizabeth-specific labels only.

---

### Task 1: Parity Audit

**Files:**
- Create: `docs/superpowers/audits/2026-07-08-ericcole-parity-audit.md`

- [ ] **Step 1: Generate a commit/topic list from Eric Cole**

Run:

```powershell
git -C C:/Users/Asus/Desktop/Гитхабелизбает/Ericcole log --oneline --decorate -40
git -C C:/Users/Asus/Desktop/Гитхабелизбает/elizabethvane log --oneline --decorate -40
```

Expected: Eric includes recent commits such as `Allow Telegram admins with rotated admin token`, `Restore admin entry and user avatars`, `Restore binary news block`, Pocket/AIO/Chatterfy changes; Elizabeth lacks at least some of them.

- [ ] **Step 2: Diff key files without applying changes**

Run:

```powershell
git --no-pager -C C:/Users/Asus/Desktop/Гитхабелизбает diff --no-index --stat Ericcole/backend/main.py elizabethvane/backend/main.py
git --no-pager -C C:/Users/Asus/Desktop/Гитхабелизбает diff --no-index --stat Ericcole/backend/db_bootstrap.py elizabethvane/backend/db_bootstrap.py
git --no-pager -C C:/Users/Asus/Desktop/Гитхабелизбает diff --no-index --stat Ericcole/frontend/src/components/pages/Profile.jsx elizabethvane/frontend/src/components/pages/Profile.jsx
git --no-pager -C C:/Users/Asus/Desktop/Гитхабелизбает diff --no-index --stat Ericcole/frontend/src/admin/pages/UsersPage.jsx elizabethvane/frontend/src/admin/pages/UsersPage.jsx
```

Expected: command may exit `1` because files differ; record the stats, not as a failure.

- [ ] **Step 3: Write the audit file**

Create `docs/superpowers/audits/2026-07-08-ericcole-parity-audit.md` with this structure:

```markdown
# Eric Cole Parity Audit For Elizabeth Vane

## Backend Missing Or Older

- Admin token rotation behavior:
- Profile avatar/admin payload:
- Pocket postback intake:
- AIO forwarding:
- Chatterfy forwarding:
- Access policy:
- Signal indicator normalization:

## Frontend Missing Or Older

- Profile Telegram avatar:
- Admin user avatar:
- Binary news block:
- Strategy indicator settings:
- Access policy settings:

## Elizabeth-Specific Values To Preserve

- Brand: Elizabeth Vane
- Bot username:
- Web app URL:
- Channel/support links:
- AIO UUIDs:
- Chatterfy endpoints:
- Pocket secret:
- Test/prod deploy paths:
```

- [ ] **Step 4: Commit the audit**

Run:

```powershell
git add docs/superpowers/audits/2026-07-08-ericcole-parity-audit.md
git commit -m "Audit Eric parity gaps"
```

Expected: commit succeeds and contains only the audit file.

---

### Task 2: Backend Admin And Avatar Parity

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/tests/test_profile_admin_avatar.py` or create it if missing

- [ ] **Step 1: Write failing regression tests**

Add `backend/tests/test_profile_admin_avatar.py`:

```python
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ProfileAdminAvatarTest(unittest.TestCase):
    def test_profile_api_returns_admin_status_and_url(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("AS is_admin", source)
        self.assertIn("admin_url", source)
        self.assertIn("build_admin_webapp_url()", source)

    def test_admin_auth_allows_authenticated_telegram_admins_with_stale_token(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        start = source.index("async def get_admin_user(")
        end = source.index("async def get_stream_settings_row", start)
        block = source[start:end]

        self.assertLess(block.index("is_admin_user"), block.index("get_admin_panel_token"))
        self.assertIn("admin buttons working", block)

    def test_sync_does_not_overwrite_existing_avatar_with_empty_value(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("NULLIF(VALUES(avatar_url), '')", source)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify current gap**

Run:

```powershell
$env:PYTHONPATH='backend'
& 'C:/Users/Asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest backend.tests.test_profile_admin_avatar
```

Expected before implementation: fails if Elizabeth lacks one of these behaviors.

- [ ] **Step 3: Port backend behavior**

Modify `backend/main.py`:

- In `get_admin_user`, check `is_admin_user(int(user["user_id"]))` before token comparison.
- Allow active Telegram admins even if `X-Admin-Token` is missing/stale.
- In `/api/user/profile`, include `CASE WHEN a.user_id IS NULL THEN 0 ELSE a.is_active END AS is_admin`, join `admin_users`, and add `admin_url`.
- In `/api/user/sync`, update avatar with `avatar_url = COALESCE(NULLIF(VALUES(avatar_url), ''), avatar_url)`.

Use this target shape for `get_admin_user`:

```python
async def get_admin_user(
    user=Depends(get_telegram_user),
    x_admin_token: str = Header(default="", alias="X-Admin-Token"),
):
    if not await is_admin_user(int(user["user_id"])):
        raise HTTPException(status_code=403, detail="Admin access denied")

    expected = get_admin_panel_token()
    provided = (x_admin_token or "").strip()
    if provided and secrets.compare_digest(provided, expected):
        return user

    # Telegram WebApp initData already proves the user identity; keep old
    # admin buttons working even if their URL token was rotated by a deploy.
    return user
```

- [ ] **Step 4: Run tests**

Run:

```powershell
$env:PYTHONPATH='backend'
& 'C:/Users/Asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest backend.tests.test_profile_admin_avatar
```

Expected: `OK`.

- [ ] **Step 5: Commit**

Run:

```powershell
git add backend/main.py backend/tests/test_profile_admin_avatar.py
git commit -m "Restore admin profile payload and avatars"
```

---

### Task 3: Frontend Profile And Admin User Avatars

**Files:**
- Modify: `frontend/src/components/pages/Profile.jsx`
- Modify: `frontend/src/components/pages/Profile.css`
- Modify: `frontend/src/admin/pages/UsersPage.jsx`
- Modify: `frontend/src/admin/admin.css`
- Modify: `backend/tests/test_profile_admin_avatar.py`

- [ ] **Step 1: Extend regression test**

Add these test methods to `backend/tests/test_profile_admin_avatar.py`:

```python
    def test_profile_uses_user_avatar_url(self):
        source = (PROJECT_ROOT / "frontend/src/components/pages/Profile.jsx").read_text(encoding="utf-8")

        self.assertIn("user.avatar_url", source)
        self.assertIn("avatarBroken", source)
        self.assertNotIn("eric-avatar.jpg", source)

    def test_admin_users_render_user_avatar(self):
        source = (PROJECT_ROOT / "frontend/src/admin/pages/UsersPage.jsx").read_text(encoding="utf-8")

        self.assertIn("getAvatarUrl", source)
        self.assertIn("admin-user-avatar", source)
```

For Elizabeth, also assert the Elizabeth default import is not used in `Profile.jsx`:

```python
        self.assertNotIn("elizabeth-avatar.jpg", source)
```

- [ ] **Step 2: Run test to verify current gap**

Run:

```powershell
$env:PYTHONPATH='backend'
& 'C:/Users/Asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest backend.tests.test_profile_admin_avatar
```

Expected before implementation: fails if frontend still imports the default avatar image.

- [ ] **Step 3: Update profile**

In `frontend/src/components/pages/Profile.jsx`:

- remove `import avatarImg from '../../assets/elizabeth-avatar.jpg';`;
- add `avatarBroken` state;
- derive `avatarUrl` from `user.avatar_url`;
- render `<img src={avatarUrl}>` when available;
- render initials fallback otherwise;
- render an `Admin Center` button when `Number(user.is_admin) === 1 && user.admin_url`.

Keep the visible name `Elizabeth Vane`.

- [ ] **Step 4: Update admin user list**

In `frontend/src/admin/pages/UsersPage.jsx`, add:

```javascript
const getAvatarUrl = (user) => String(user?.avatar_url || '').trim();
const getInitials = (user) => String(user?.first_name || user?.username || user?.user_id || 'U')
  .trim()
  .slice(0, 2)
  .toUpperCase();
```

Render `.admin-user-avatar` in list items and selected user card. Always render initials underneath and overlay the image when it loads; hide broken images in `onError`.

- [ ] **Step 5: Add CSS**

In `Profile.css`, style `.profile-avatar-placeholder` as a circular initials fallback and add `.admin-center-profile-btn`.

In `admin.css`, add `.admin-user-avatar`, `.admin-user-avatar.large`, `.admin-user-avatar img`, `.admin-user-title-row`.

- [ ] **Step 6: Run tests and frontend build**

Run:

```powershell
$env:PYTHONPATH='backend'
& 'C:/Users/Asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest backend.tests.test_profile_admin_avatar
& 'C:/Users/Asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' frontend/node_modules/vite/bin/vite.js build
```

Expected: tests pass and Vite build succeeds.

- [ ] **Step 7: Commit**

Run:

```powershell
git add frontend/src/components/pages/Profile.jsx frontend/src/components/pages/Profile.css frontend/src/admin/pages/UsersPage.jsx frontend/src/admin/admin.css backend/tests/test_profile_admin_avatar.py
git commit -m "Show Telegram avatars in Elizabeth app"
```

---

### Task 4: Pocket Postback Intake And Metadata

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/db_bootstrap.py`
- Create or modify: `backend/tests/test_chatterfy_pocket.py`
- Create or modify: `backend/tests/test_pocket_postback.py`

- [ ] **Step 1: Compare Eric and Elizabeth helpers**

Run:

```powershell
rg -n "pocket/postback|POCKET_POSTBACK|sub_id2|pocket_sub_id2|registration|first_deposit|repeat_deposit" C:/Users/Asus/Desktop/Гитхабелизбает/Ericcole/backend C:/Users/Asus/Desktop/Гитхабелизбает/elizabethvane/backend
```

Expected: identify exact Eric handlers missing or older in Elizabeth.

- [ ] **Step 2: Add tests for metadata extraction**

Create or update `backend/tests/test_pocket_postback.py`:

```python
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class PocketPostbackSourceTest(unittest.TestCase):
    def test_pocket_postback_accepts_registration_ftd_and_deposit(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("/api/integrations/pocket/postback", source)
        self.assertIn("registration", source)
        self.assertIn("ftd", source)
        self.assertIn("dep", source)

    def test_pocket_postback_stores_tracking_metadata(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        for field in (
            "pocket_click_id",
            "pocket_site_id",
            "pocket_cid",
            "pocket_sub_id1",
            "pocket_sub_id2",
            "trader_id",
        ):
            self.assertIn(field, source)

    def test_schema_has_pocket_tracking_columns(self):
        source = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(encoding="utf-8")

        for field in (
            "pocket_click_id",
            "pocket_site_id",
            "pocket_cid",
            "pocket_sub_id1",
            "pocket_sub_id2",
            "pocket_deposit_amount",
        ):
            self.assertIn(field, source)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Port schema additions**

In `backend/db_bootstrap.py`, ensure idempotent columns exist on `users`:

```python
await _ensure_column(conn, db_name, "users", "pocket_click_id", "ALTER TABLE users ADD COLUMN pocket_click_id VARCHAR(64) NULL")
await _ensure_column(conn, db_name, "users", "pocket_site_id", "ALTER TABLE users ADD COLUMN pocket_site_id VARCHAR(128) NULL")
await _ensure_column(conn, db_name, "users", "pocket_cid", "ALTER TABLE users ADD COLUMN pocket_cid VARCHAR(128) NULL")
await _ensure_column(conn, db_name, "users", "pocket_sub_id1", "ALTER TABLE users ADD COLUMN pocket_sub_id1 VARCHAR(255) NULL")
await _ensure_column(conn, db_name, "users", "pocket_sub_id2", "ALTER TABLE users ADD COLUMN pocket_sub_id2 VARCHAR(255) NULL")
await _ensure_column(conn, db_name, "users", "pocket_registered", "ALTER TABLE users ADD COLUMN pocket_registered TINYINT(1) NOT NULL DEFAULT 0")
await _ensure_column(conn, db_name, "users", "pocket_deposited", "ALTER TABLE users ADD COLUMN pocket_deposited TINYINT(1) NOT NULL DEFAULT 0")
await _ensure_column(conn, db_name, "users", "pocket_deposit_amount", "ALTER TABLE users ADD COLUMN pocket_deposit_amount DECIMAL(18,2) NOT NULL DEFAULT 0.00")
```

Skip lines that already exist in Elizabeth.

- [ ] **Step 4: Port postback handler**

In `backend/main.py`, port Eric's Pocket postback route into Elizabeth. Keep Elizabeth secrets from env and do not hard-code Eric values.

Expected external URL shape:

```text
https://<elizabeth-app-domain>/api/integrations/pocket/postback?secret=<ELIZABETH_SECRET>&event=registration&click_id={click_id}&site_id={site_id}&trader_id={trader_id}&cid={cid}&sub_id1={sub_id1}&sub_id2={sub_id2}
```

Deposit URLs use `event=ftd` or `event=dep` and include `sumdep={sumdep}`.

- [ ] **Step 5: Run tests**

Run:

```powershell
$env:PYTHONPATH='backend'
& 'C:/Users/Asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest backend.tests.test_pocket_postback
```

Expected: `OK`.

- [ ] **Step 6: Commit**

Run:

```powershell
git add backend/main.py backend/db_bootstrap.py backend/tests/test_pocket_postback.py
git commit -m "Accept Pocket postbacks in Elizabeth"
```

---

### Task 5: AIO And Chatterfy Forwarding

**Files:**
- Modify or create: `backend/aio_tracking.py`
- Modify or create: `backend/chatterfy_tracking.py`
- Modify or create: `backend/chatterfy_pocket.py`
- Modify: `backend/main.py`
- Modify: `backend/tests/test_aio_tracking.py`
- Modify: `backend/tests/test_chatterfy_tracking.py`
- Modify: `backend/tests/test_chatterfy_pocket.py`

- [ ] **Step 1: Port helper tests from Eric**

Compare:

```powershell
git --no-pager -C C:/Users/Asus/Desktop/Гитхабелизбает diff --no-index Ericcole/backend/tests/test_aio_tracking.py elizabethvane/backend/tests/test_aio_tracking.py
git --no-pager -C C:/Users/Asus/Desktop/Гитхабелизбает diff --no-index Ericcole/backend/tests/test_chatterfy_tracking.py elizabethvane/backend/tests/test_chatterfy_tracking.py
git --no-pager -C C:/Users/Asus/Desktop/Гитхабелизбает diff --no-index Ericcole/backend/tests/test_chatterfy_pocket.py elizabethvane/backend/tests/test_chatterfy_pocket.py
```

Expected: identify missing assertions and copy tests with Elizabeth-neutral names.

- [ ] **Step 2: Port URL builder behavior**

Ensure AIO registration URL builder produces:

```text
https://app.aio.tech/api/v1/trigger/conversion-request?visit_uuid={aio_visit_uuid}&conversion_type_uuid=<ELIZABETH_REG_UUID>&tgid={tgid}&tg_trader_id={trader_id}
```

Ensure FTD URL builder includes:

```text
conversion_type_uuid=<ELIZABETH_FTD_UUID>&arrived_revenue={revenue}&tgid={tgid}&tg_trader_id={trader_id}
```

Ensure DEP URL builder includes:

```text
conversion_type_uuid=<ELIZABETH_DEP_UUID>&arrived_revenue={revenue}&tgid={tgid}&tg_trader_id={trader_id}
```

UUIDs must come from Elizabeth env/settings, not Eric constants.

- [ ] **Step 3: Port Chatterfy forwarding**

Ensure Pocket registration/FTD/DEP can also call Elizabeth Chatterfy custom endpoint when configured. `clickid` must come from stored `pocket_sub_id2`.

Expected payload mapping:

```text
clickid = user.pocket_sub_id2
fields.trader_id = user.trader_id
fields.trader_aio_id = user.aio_visit_uuid
fields.tgid = user.user_id
```

- [ ] **Step 4: Run tests**

Run:

```powershell
$env:PYTHONPATH='backend'
& 'C:/Users/Asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest backend.tests.test_aio_tracking backend.tests.test_chatterfy_tracking backend.tests.test_chatterfy_pocket
```

Expected: `OK`.

- [ ] **Step 5: Commit**

Run:

```powershell
git add backend/aio_tracking.py backend/chatterfy_tracking.py backend/chatterfy_pocket.py backend/main.py backend/tests/test_aio_tracking.py backend/tests/test_chatterfy_tracking.py backend/tests/test_chatterfy_pocket.py
git commit -m "Forward Elizabeth Pocket events to AIO and Chatterfy"
```

---

### Task 6: Access Policy Settings

**Files:**
- Modify or create: `backend/access_policy.py`
- Modify: `backend/db_bootstrap.py`
- Modify: `backend/main.py`
- Modify: `frontend/src/admin/pages/SettingsPage.jsx`
- Modify: `backend/tests/test_access_policy.py`

- [ ] **Step 1: Port access policy tests**

Ensure `backend/tests/test_access_policy.py` covers:

```python
from access_policy import can_user_access_signals


def test_open_policy_allows_everyone():
    assert can_user_access_signals({"policy": "open"}, {"pocket_registered": 0, "pocket_deposit_amount": 0}) is True


def test_registration_policy_requires_registration():
    assert can_user_access_signals({"policy": "registration"}, {"pocket_registered": 1, "pocket_deposit_amount": 0}) is True
    assert can_user_access_signals({"policy": "registration"}, {"pocket_registered": 0, "pocket_deposit_amount": 100}) is False


def test_registration_deposit_policy_requires_min_total_deposit():
    settings = {"policy": "registration_deposit", "min_deposit_amount": 100}
    assert can_user_access_signals(settings, {"pocket_registered": 1, "pocket_deposit_amount": 100}) is True
    assert can_user_access_signals(settings, {"pocket_registered": 1, "pocket_deposit_amount": 99.99}) is False
```

- [ ] **Step 2: Port settings schema**

Ensure `admin_system_access_settings` exists and has:

```sql
policy VARCHAR(32) NOT NULL DEFAULT 'registration_deposit'
min_deposit_amount DECIMAL(18,2) NOT NULL DEFAULT 0.00
updated_by BIGINT NULL
updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
```

- [ ] **Step 3: Port backend settings endpoints**

Update `/api/admin/settings` and `/api/admin/settings` POST to read/write:

```json
{
  "system_access": {
    "policy": "registration_deposit",
    "min_deposit_amount": 100
  }
}
```

Allowed policies:

```python
{"open", "registration", "registration_deposit"}
```

- [ ] **Step 4: Port frontend settings section**

In `SettingsPage.jsx`, render three choices:

- `Доступ открыт всем`
- `После регистрации`
- `После регистрации и депозита`

When `registration_deposit` is selected, show a minimum deposit input.

- [ ] **Step 5: Run tests and build**

Run:

```powershell
$env:PYTHONPATH='backend'
& 'C:/Users/Asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest backend.tests.test_access_policy
& 'C:/Users/Asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' frontend/node_modules/vite/bin/vite.js build
```

Expected: tests pass and frontend builds.

- [ ] **Step 6: Commit**

Run:

```powershell
git add backend/access_policy.py backend/db_bootstrap.py backend/main.py frontend/src/admin/pages/SettingsPage.jsx backend/tests/test_access_policy.py
git commit -m "Add Elizabeth signal access policies"
```

---

### Task 7: Signal Result Parity

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/analysis_runtime.py`
- Modify: `backend/stream_matching.py`
- Modify: `frontend/src/components/binary/BinarySignalSettings.jsx`
- Modify: `frontend/src/components/forex/ForexAnalysisSettings.jsx`
- Modify: `frontend/src/admin/pages/SettingsPage.jsx`
- Modify: `backend/tests/test_frontend_news_blocks.py`
- Modify: `backend/tests/test_strategy_indicators.py`
- Modify: `backend/tests/test_stream_matching.py`

- [ ] **Step 1: Port source tests**

Ensure tests check:

```python
self.assertIn("news-filter-block", binary_source)
self.assertIn("NewsModal", binary_source)
self.assertIn("getFilteredNewsStatus", binary_source)
self.assertNotIn("Configured", rendered_missing_indicator_logic)
```

Use Eric tests as reference and keep Elizabeth component paths.

- [ ] **Step 2: Port binary news block**

In `BinarySignalSettings.jsx`, ensure:

- `NewsModal` is imported;
- response `news_data` is stored;
- result renders `.news-filter-block`;
- click opens news modal.

- [ ] **Step 3: Port configured indicator values**

Ensure manually configured stream indicator values display actual admin values and do not render `Configured` as a user-facing value.

Expected behavior:

- if admin sets indicator direction only, show direction and neutral numeric fallback if available;
- if admin sets custom value, show custom value;
- if value is unavailable, omit that indicator rather than showing broken placeholder text.

- [ ] **Step 4: Run tests and build**

Run:

```powershell
$env:PYTHONPATH='backend'
& 'C:/Users/Asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest backend.tests.test_frontend_news_blocks backend.tests.test_strategy_indicators backend.tests.test_stream_matching
& 'C:/Users/Asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' frontend/node_modules/vite/bin/vite.js build
```

Expected: tests pass and frontend builds.

- [ ] **Step 5: Commit**

Run:

```powershell
git add backend/main.py backend/analysis_runtime.py backend/stream_matching.py frontend/src/components/binary/BinarySignalSettings.jsx frontend/src/components/forex/ForexAnalysisSettings.jsx frontend/src/admin/pages/SettingsPage.jsx backend/tests/test_frontend_news_blocks.py backend/tests/test_strategy_indicators.py backend/tests/test_stream_matching.py
git commit -m "Match Eric signal result behavior"
```

---

### Task 8: Full Verification

**Files:**
- No code files unless failures require fixes.

- [ ] **Step 1: Run all backend tests**

Run:

```powershell
$env:PYTHONPATH='backend'
& 'C:/Users/Asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest discover backend/tests
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend production build**

Run:

```powershell
& 'C:/Users/Asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' frontend/node_modules/vite/bin/vite.js build
```

Expected: Vite build succeeds. Existing chunk-size and lottie eval warnings are acceptable if unchanged.

- [ ] **Step 3: Check git diff**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors; status clean after commits.

- [ ] **Step 4: Commit any verification fixes**

If fixes were needed, run:

```powershell
git add <changed-files>
git commit -m "Stabilize Elizabeth parity migration"
```

Expected: no uncommitted files remain.

---

### Task 9: Test Deployment

**Files:**
- No repository files unless deployment docs are updated.

- [ ] **Step 1: Confirm Elizabeth deployment paths**

Run or inspect existing notes/server:

```powershell
ssh root@<ELIZABETH_SERVER> "find /opt /root /var/www -maxdepth 4 -iname '*elizabeth*' -o -iname '*vane*' 2>/dev/null | head -80"
```

Expected: identify Elizabeth test repository path, runtime backend path, frontend dist path, and supervisor process name.

- [ ] **Step 2: Fast-forward test branch**

Run:

```powershell
git checkout test
git merge --ff-only main
git push origin test
git checkout main
```

Expected: test branch points to the migration commits.

- [ ] **Step 3: Deploy test**

Use Elizabeth paths discovered in Step 1. Command shape:

```bash
set -e
cd <ELIZABETH_TEST_REPO>
git pull --ff-only origin test
cd frontend
npm run build
rsync -a --delete dist/ <ELIZABETH_TEST_DIST>/
rsync -a --delete --exclude .env <ELIZABETH_TEST_REPO>/backend/ <ELIZABETH_TEST_RUNTIME>/
python3 -m py_compile <ELIZABETH_TEST_RUNTIME>/main.py <ELIZABETH_TEST_RUNTIME>/db_bootstrap.py
supervisorctl restart <ELIZABETH_TEST_PROCESS>
supervisorctl status <ELIZABETH_TEST_PROCESS>
```

Expected: process is `RUNNING`.

- [ ] **Step 4: Smoke check test**

Run:

```bash
curl -fsS http://127.0.0.1:<ELIZABETH_TEST_PORT>/api/support/links
supervisorctl status <ELIZABETH_TEST_PROCESS>
```

Expected: JSON support links and `RUNNING`.

---

### Task 10: Production Deployment

**Files:**
- No repository files unless deployment docs are updated.

- [ ] **Step 1: Deploy production**

Use Elizabeth production paths discovered in Task 9. Command shape:

```bash
set -e
cd <ELIZABETH_PROD_REPO>
git pull --ff-only origin main
cd frontend
npm run build
rsync -a --delete dist/ <ELIZABETH_PROD_DIST>/
rsync -a --delete --exclude .env <ELIZABETH_PROD_REPO>/backend/ <ELIZABETH_PROD_RUNTIME>/
python3 -m py_compile <ELIZABETH_PROD_RUNTIME>/main.py <ELIZABETH_PROD_RUNTIME>/db_bootstrap.py
supervisorctl restart <ELIZABETH_PROD_PROCESS>
supervisorctl status <ELIZABETH_PROD_PROCESS>
```

Expected: process is `RUNNING`.

- [ ] **Step 2: Smoke check production**

Run:

```bash
curl -fsS http://127.0.0.1:<ELIZABETH_PROD_PORT>/api/support/links
supervisorctl status <ELIZABETH_TEST_PROCESS> <ELIZABETH_PROD_PROCESS>
```

Expected: JSON support links and both processes `RUNNING`.

- [ ] **Step 3: Final report**

Report:

```text
Migrated Elizabeth to Eric parity.
Commits:
- <commit list>
Verified:
- backend tests
- frontend build
- test deploy
- prod deploy
Notes:
- Elizabeth-specific values preserved
- External UUIDs/secrets requiring admin configuration
```

