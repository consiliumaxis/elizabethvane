# Eric Cole Parity Migration For Elizabeth Vane

## Goal

Bring the Elizabeth Vane project to feature parity with the current Eric Cole production code, while preserving Elizabeth-specific branding, domains, bot names, channel/support links, AIO/Chatterfy identifiers, database names, and deployment targets.

The migration must not blindly overwrite Elizabeth with Eric Cole. Eric Cole is the reference implementation; Elizabeth keeps its own project identity.

## Scope

Migrate these Eric Cole capabilities into Elizabeth where missing or older:

- Admin access and admin WebApp flow, including tolerance for rotated admin URL tokens when Telegram WebApp initData identifies an active admin.
- Telegram user avatars in the app profile and admin user cards, with no overwrite of existing avatars by empty Telegram payloads.
- Binary and Forex news blocks in result screens.
- Strategy indicator filtering fixes, configured indicator value display, and removal of missing placeholder values.
- Custom stream indicator values and local stream analysis for configured assets.
- Pocket registration, FTD, and repeat deposit postback intake.
- Pocket metadata storage on users: click_id, site_id, trader_id, cid, sub_id1, sub_id2 as Chatterfy clickid.
- Forwarding registration, FTD, and repeat deposit events to AIO using the current conversion-request URLs pattern.
- Forwarding Pocket events to Chatterfy custom postback where configured.
- Access policy logic: open to all, after registration, or after registration plus minimum total deposit.
- Chatterfy events and logs where Elizabeth uses the same funnel model.
- Quiz skip completion behavior and postback idempotency/logging patterns.

Out of scope unless explicitly requested:

- Replacing Elizabeth visual identity with Eric Cole visuals.
- Reusing Eric Cole production secrets, domains, campaign UUIDs, Telegram channel IDs, or bot usernames.
- Changing Elizabeth deployment topology beyond what is needed to deploy the migrated code.

## Approach

Use Eric Cole as a source-of-truth diff, but port by feature area:

1. Compare each relevant Eric Cole commit/function/table with the Elizabeth version.
2. Apply the smallest Elizabeth-native patch that preserves existing Elizabeth behavior.
3. Add or port regression tests for each feature area.
4. Deploy to Elizabeth test first, verify, then merge/deploy production.

This avoids a risky full directory replacement and protects Elizabeth-specific config.

## Components

### Backend

Update `backend/main.py`, support modules, and `backend/db_bootstrap.py` as needed. Schema changes must be additive and idempotent through `ensure_database_schema`.

The backend owns:

- admin authentication and `/api/admin/*`;
- `/api/user/profile` payload shape;
- Pocket postback intake;
- AIO/Chatterfy forwarding;
- access policy evaluation;
- balance and deposit state;
- signal generation result normalization.

### Frontend

Update `frontend/src` components in the existing Elizabeth style:

- profile avatar/admin entry;
- admin settings and user cards;
- signal/news result blocks;
- strategy and stream settings.

UI labels must remain Elizabeth Vane, not Eric Cole.

### Database

Keep Elizabeth DB data. New columns/tables should be additive. Existing users, strategies, admins, support links, and Pocket settings must not be wiped.

Important user identity mapping:

- Pocket `click_id` maps to Telegram user id where configured.
- Pocket `sub_id2` is stored and shown as Chatterfy clickid.
- AIO visit UUID remains the key for AIO conversion forwarding when available.

## Error Handling

- Missing AIO visit UUID should skip AIO forwarding and log the reason.
- Duplicate events should be idempotent per user/event/source key.
- Invalid external postback secrets should be rejected.
- Pocket postbacks without a matching user should be logged and skipped, not crash the service.
- Admin access should deny non-admin Telegram users even if a URL token is present.

## Testing

Port or create focused tests for:

- admin token rotation behavior;
- profile/admin user avatars;
- Pocket postback URL parsing and metadata persistence;
- AIO registration/FTD/DEP URL builders;
- Chatterfy forwarding response handling;
- access policy decisions;
- strategy indicator filtering and configured values;
- binary and forex news block source checks.

Run:

- backend unit tests with `PYTHONPATH=backend`;
- frontend production build;
- server-side `py_compile`;
- test deployment smoke checks before production.

## Deployment

Follow the established workflow:

1. Commit Elizabeth changes on `main`.
2. Fast-forward `test` from `main`.
3. Push `test`.
4. Deploy Elizabeth test and verify.
5. Push/confirm `main`.
6. Deploy Elizabeth production and verify.

The exact Elizabeth server paths must be confirmed before deployment. Do not reuse Eric Cole paths.

## Open Decisions

- Confirm Elizabeth AIO conversion type UUIDs for registration, FTD, and repeat deposit.
- Confirm Elizabeth Chatterfy custom postback endpoint and event slugs.
- Confirm Elizabeth Pocket postback secret and final Pocket postback URLs.
- Confirm Elizabeth test/prod server paths and supervisor process names.
