# Discord bot practices and current integration review

Reviewed against official documentation on 2026-09-26. This project is a self-hosted, server-installed signal bot, not a hosted public service. Recheck Discord requirements before a public rollout because platform policy and rate limits can change.

## Recommended installation and permissions

1. Create an application in the Discord Developer Portal and use its bot user. Install for server use with the `bot` and `applications.commands` scopes. Discord currently auto-includes `applications.commands` with `bot`, but listing both makes the install intent explicit.
2. Request only the permissions needed to read the selected channel and post an alert: `View Channels`, `Send Messages`, and `Embed Links`. Do not request Administrator.
3. Use slash/application commands. Enable only the non-privileged `GUILDS` Gateway intent so the library can maintain server/channel context and receive guild lifecycle events. This tracker does not need message-content, member-list, or presence access; leave those and all privileged Gateway intents disabled.
4. Keep the bot token in `.env`/a secret store, never in source, logs, screenshots, or Git. If it is exposed or lost, reset it in the Developer Portal and update the runtime secret.
5. Register an application only after the feature is ready for its target audience. Discord says app verification is required to scale past 100 servers. This bot does not need privileged intents; the separate privileged-intent review threshold does not apply unless a future feature asks for one.

## Notification delivery and scale

- Configure one destination channel per server. The bot sends one message to that channel for a signal; Discord handles distribution to members and their push/desktop settings. The bot should not enumerate or message every member individually.
- A member gets a notification only according to their Discord settings. Channel/server options include all messages, mentions only, nothing, or mute, and device-level push settings also matter. With mentions disabled, users who choose all messages can receive alerts; users set to mentions only should not expect a ping.
- Keep `allowed_mentions` disabled by default so text from a public post cannot ping users, roles, `@everyone`, or `@here`. If users later request pings, make it an explicit opt-in role feature with a visible server-level configuration and test that it never broadens to everyone.
- Python with `asyncio` and `discord.py` is appropriate for this mostly network-I/O workload. There is no Discord-mandated language. For this product, polling/X access, delivery volume, uptime, and Discord API rate limits are more relevant than switching languages.
- Fan-out grows with the number of configured guild channels, not with the total number of people who read a channel. Each server destination still requires a Discord message request. Discord documents a global API limit of 50 requests/second plus per-route limits; limits can change. Let a maintained library handle buckets, honor `Retry-After` on 429s, avoid blind retry loops, and record partial delivery failures. Do not hard-code a per-channel rate limit.
- Successful deliveries are persisted per guild so a later scan can retry failed destinations without duplicating the alert to guilds that already received it. The retry depends on the source post appearing again in the tracker results. Before broad rollout, add a durable outbox independent of polling so delayed failures cannot be lost after the post leaves the scan window; preserve idempotency and monitor pending deliveries.

## Slash commands and policy

- Keep administrative configuration behind server-side permissions (`Manage Server`/`MANAGE_GUILD` as appropriate). Give a clear ephemeral response to command users, and check the bot can view/send/embed in the selected destination.
- Discord requires an initial interaction response within 3 seconds; defer long-running work, then follow up while the interaction token remains valid.
- Respect opt-in and opt-out. This project posts only to an admin-configured channel, offers `/stop-alerts`, and should not send unsolicited direct messages or spam. `/set-alert-channel` selects the destination, `/reset-bot-status` checks the setup, `/test-reset-alert` posts one explicitly synthetic test message, `/preview-reset-alert` shows a private preview, and `/reset-bot-help` explains the commands. Do not automate ordinary user accounts; use the official bot API.
- `CODQ_DISCORD_TEST_GUILD_ID` optionally syncs slash commands to a single development guild for quick testing; omit it to register commands globally.
- Filter and escape untrusted external text; preserve the source URL; distinguish Codex from Claude/Anthropic; describe inferred reset windows as estimates rather than promises. Do not claim that a public post guarantees account eligibility or an actual quota reset.

## Avatar and brand assets

Set the app icon in the Developer Portal under **General Information**. The bot user avatar can also be updated at runtime: `discord.py` exposes `ClientUser.edit(avatar=...)` with image bytes, and Discord documents an avatar field on the current-user edit endpoint. Prefer the portal for a stable avatar; loading a local asset into the program is not required for normal operation. Keep the app icon and bot profile visually consistent and legible when cropped to a small circle.

## Current presentation review

The repository has no Discord screenshot yet. Its existing images show Telegram and Windows desktop notifications. The Telegram example in `assets/telegram_noti_example.JPG` is visibly cluttered and includes raw regular-expression rules in `Matched`. The matcher stores those rule strings in `TweetMatch.matched_patterns`; the Discord embed now suppresses those implementation details and shows a concise reset-signal label instead.

The Discord card uses provider-specific color, author/source identity, a short human-readable signal label, a concise escaped excerpt, an estimated reset window when present, and a direct link to the original X post. It marks the signal as unofficial and tells readers to verify the source. `/test-reset-alert` provides an ephemeral preview without posting noise into the alert channel. A live screenshot in both Discord themes and on mobile remains useful before a public rollout.

## Official references

- [Discord: Building your first bot](https://docs.discord.com/developers/quick-start/getting-started)
- [Discord: Gateway intents and privileged intents](https://docs.discord.com/developers/events/gateway#privileged-intents)
- [Discord: Application/slash commands](https://docs.discord.com/developers/docs/interactions/slash-commands)
- [Discord: Responding to interactions and the initial response deadline](https://docs.discord.com/developers/interactions/receiving-and-responding)
- [Discord: Message, embed limits, allowed mentions, and message creation](https://docs.discord.com/developers/resources/message)
- [Discord: API rate limits](https://docs.discord.com/developers/topics/rate-limits)
- [Discord: Developer Policy](https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy)
- [Discord: app verification requirement](https://support-dev.discord.com/hc/en-us/articles/23926564536471-How-Do-I-Get-My-App-Verified)
- [Discord Help Center: notification settings](https://support.discord.com/hc/en-us/articles/215253258-Notifications-Settings-101)
- [Discord: User Resource, including the current-user avatar update](https://docs.discord.com/developers/resources/user#modify-current-user)
- [discord.py: introduction](https://discordpy.readthedocs.io/en/stable/intro.html), [ClientUser avatar editing](https://discordpy.readthedocs.io/en/stable/api.html#discord.ClientUser.edit), and [FAQ](https://discordpy.readthedocs.io/en/stable/faq.html)
