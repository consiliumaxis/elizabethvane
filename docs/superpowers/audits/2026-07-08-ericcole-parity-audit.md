# Eric Cole Parity Audit For Elizabeth Vane

## Backend Missing Or Older

- Admin token rotation behavior: Eric allows a valid Telegram WebApp admin through even when the URL admin token is stale; Elizabeth still checks the token before accepting the admin.
- Profile avatar/admin payload: Eric returns `is_admin` and `admin_url` from `/api/user/profile` and preserves existing `avatar_url` when Telegram sends an empty photo; Elizabeth returns `avatar_url` but does not expose the admin payload and can overwrite avatar with empty data.
- Pocket postback intake: Eric accepts `/api/integrations/pocket/postback` for registration, FTD, and repeat deposit; Elizabeth has Pocket API/balance controls but not the full postback intake chain.
- AIO forwarding: Eric forwards registration, FTD, and DEP to AIO conversion-request URLs; Elizabeth does not yet have the same forwarding helpers.
- Chatterfy forwarding: Eric stores Chatterfy clickid from Pocket `sub_id2` and forwards Pocket events to Chatterfy when configured; Elizabeth is missing or older here.
- Access policy: Eric supports open, registration, and registration plus minimum total deposit; Elizabeth still has older access toggles.
- Signal indicator normalization: Elizabeth already contains most configured stream value work, but needs verification against Eric for missing placeholder removal and binary news parity.

## Frontend Missing Or Older

- Profile Telegram avatar: Elizabeth profile still imports `elizabeth-avatar.jpg` instead of using `user.avatar_url`.
- Admin user avatar: Elizabeth admin user list/card does not render Telegram avatars.
- Binary news block: Forex has a news block, but binary result parity must be checked against Eric's restored `news-filter-block`.
- Strategy indicator settings: Elizabeth already has recent custom stream indicator commits; verify exact Eric parity before changing.
- Access policy settings: Elizabeth needs the three policy choices and minimum deposit input from Eric.

## Elizabeth-Specific Values To Preserve

- Brand: Elizabeth Vane.
- Bot username: keep Elizabeth bot username from environment.
- Web app URL: keep Elizabeth web app URL from environment.
- Channel/support links: keep Elizabeth admin-configured links.
- AIO UUIDs: configure Elizabeth-specific conversion UUIDs; do not copy Eric UUIDs.
- Chatterfy endpoints: configure Elizabeth-specific endpoint; do not copy Eric endpoint.
- Pocket secret: configure Elizabeth-specific `POCKET_POSTBACK_SECRET`; do not copy Eric secret.
- Test/prod deploy paths: discover and use Elizabeth server paths, not Eric paths.

