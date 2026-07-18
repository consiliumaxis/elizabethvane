# Elizabeth Vane AI Telegram bot

Standalone Telegram Business AI assistant deployed as `evanechat`.

The bot uses long polling, stores conversations and settings in MySQL, and
responds to Telegram Business messages through OpenAI. Connect the bot to the
target Telegram Business account after deployment; polling alone does not grant
access to business messages.

Runtime secrets live only in `/root/evanechat/.env` and are not committed.
