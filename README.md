# Codex Reset Tracker

Watch trusted X/Twitter accounts for fresh `reset` posts and notify you by
Telegram, email, webhook, desktop popup, or stdout.

| Area | Default |
| --- | --- |
| Package runner | `uv` |
| Scraper | [Twikit](https://github.com/d60/twikit) |
| Match rule | `reset`, `resets`, `resetting`, `resetted` |
| Trust rule | tweet author must be in `polling.accounts` |
| User timezone | auto-detected from the current machine unless overridden |
| Source timezone | per-account, used for phrases like `this evening` |

## Fast Start

```bash
git clone --branch discord-bot https://github.com/LinkPhoenix/codex-reset-tracker.git
cd codex-reset-tracker
./install.sh
uv run codex-reset-tracker setup
uv run codex-reset-tracker doctor
uv run codex-reset-tracker test-notify
uv run codex-reset-tracker check
```

The first `check` is a baseline pass by default. Keep the process running to
catch newly discovered tweets:

```bash
uv run codex-reset-tracker run
```

## Setup Map

| Need | Command |
| --- | --- |
| Full first-time wizard | `uv run codex-reset-tracker setup` |
| Notification wizard only | `uv run codex-reset-tracker setup-notifications` |
| Account wizard only | `uv run codex-reset-tracker setup-accounts` |
| List tracked accounts | `uv run codex-reset-tracker accounts list` |
| Add one account | `uv run codex-reset-tracker accounts add thsottiaux --timezone America/Los_Angeles` |
| Remove one account | `uv run codex-reset-tracker accounts remove thsottiaux` |
| Refresh recommended accounts | `uv run codex-reset-tracker accounts defaults` |

`setup` writes normal settings to `config.json` and secrets to `.env`. You should
not need to hand-edit JSON for normal use.

## X/Twitter Auth

Cookies are strongly preferred. X/Twitter often blocks automated
username/password login with Cloudflare.

| Path | When to use | Setup |
| --- | --- | --- |
| Browser cookies | Recommended | export x.com cookies to `data/x_cookies.json` |
| Username/password | Fallback only | set `CODQ_X_USERNAME` and `CODQ_X_PASSWORD` in `.env` |
| TOTP secret | Only if authenticator-app 2FA is enabled | set `CODQ_X_TOTP_SECRET` |

Cookie steps:

1. Install [Cookie-Editor (Chrome Web Store)](https://chromewebstore.google.com/detail/cookie-editor/ookdjilphngeeeghgngjabigmpepanpl?hl=en-US&utm_source=ext_sidebar).
2. Open `https://x.com` and log in.
3. Click Cookie-Editor while on `x.com`.
4. Export/copy JSON.
5. Save it here:

```bash
mkdir -p data
# save the Cookie-Editor JSON as:
data/x_cookies.json
```

Do not commit or share `data/x_cookies.json`; it can grant access to your X
session.

## Notifications

| Channel | Best for | CLI setup |
| --- | --- | --- |
| Desktop | active workstation popup | `setup-notifications` -> enable desktop |
| Telegram | fastest mobile alert | `setup-notifications` -> enable Telegram |
| Email | durable fallback | `setup-notifications` -> enable email |
| Webhook | Discord webhook, Slack, ntfy, Pushover, Home Assistant | `setup-notifications` -> enable webhook |
| stdout | logs and testing | enabled by default |

Desktop is asked first in the wizard. When running inside WSL, desktop
notifications are forwarded to Windows through `powershell.exe`.

Example alert outputs:

| Telegram | Windows desktop |
| --- | --- |
| <img src="assets/telegram_noti_example.JPG" alt="Telegram notification example" width="420"> | <img src="assets/window_noti_example.JPG" alt="Windows desktop notification example" width="360"> |

Telegram quick path:

1. Message `@BotFather`.
2. Send `/newbot`.
3. Paste the token into the wizard.
4. Send any message to the new bot.
5. Let the wizard auto-detect the chat id, or paste it manually.

### Installable Discord bot

The tracker can run as a Discord application bot with per-server channel
configuration and slash commands. This mode posts Codex, Claude and Grok reset signals
to one selected text channel per server. It runs on infrastructure you control;
it is not a hosted public bot service.

1. Create an application in the [Discord Developer Portal](https://discord.com/developers/applications).
2. Under **Bot**, reset/copy the bot token. Keep it private.
3. Under **Installation**, enable guild installation and the `bot` and
   `applications.commands` scopes. Grant only **View Channels**, **Send Messages**,
   and **Embed Links**.
4. Install the application into your server, then set the token in `.env`:

   ```dotenv
   CODQ_DISCORD_BOT_TOKEN=your_bot_token
   ```

5. Install dependencies and start the bot with the tracker:

   ```bash
   uv sync
   uv run codex-reset-tracker run-discord
   ```

6. In the channel where alerts should appear, a server manager runs
   `/set-alert-channel` (or choose a channel in its option). Use
   `/test-reset-alert` to post a synthetic test message,
   `/preview-reset-alert` for a private embed preview, `/reset-bot-status` to
   check channel permissions and the last completed tracker scan,
   `/reset-bot-help` for in-Discord instructions, or `/stop-alerts` to remove
   the server subscription.

The bot registers application commands on startup and uses no privileged
Gateway intents. Channel subscriptions are stored in `data/state.sqlite3` and
survive restarts. This mode sends alerts directly through the bot; it does not
require a Discord webhook. The existing generic webhook notifier remains
available for users who prefer it.

The bot does not ping roles or `@everyone`. Members who want push notifications
should allow all messages in the alert channel and enable the relevant device
notification settings. Members using mention-only notifications will not get a
ping for an alert.

To keep the bot online, run this command on an always-on machine or server.
Protect the bot token like a password and never commit `.env`.

#### Test on a private server from Windows

This is a self-hosted bot: the Python process must stay running. For a private
test server, follow these steps on the computer that will run the tracker:

1. Install `uv` if needed. In PowerShell, the official WinGet package is:

   ```powershell
   winget install --id=astral-sh.uv -e
   ```

   See the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/)
   for other install methods.
2. In Discord's [Developer Portal](https://discord.com/developers/applications),
   create an application and add its bot user. Keep **Public Bot** disabled if
   only you should be able to add it to servers. In **Installation**, enable
   **Guild Install** with the `bot` and `applications.commands` scopes, then
   select only **View Channels**, **Send Messages**, and **Embed Links**.
   Install it in your private test server.
3. To receive real reset signals, prepare X authentication as described in
   [X/Twitter Auth](#xtwitter-auth). The synthetic Discord test works without
   X credentials; the tracker will stay connected to Discord and retry X on
   later polling intervals until authentication is available.
   Before exporting cookies, create the folder from PowerShell if needed:

   ```powershell
   New-Item -ItemType Directory -Force data
   ```
4. From the repository folder, install dependencies. Run the first-time setup
   only if neither `config.json` nor `.env` already exists:

   ```powershell
   uv sync
   ```

   If this is a new setup, also run `uv run codex-reset-tracker setup` and
   complete its prompts. The X cookie file should be at `data\x_cookies.json`.
5. Open `.env` in a text editor and add the bot token. For faster slash-command
   updates while testing, also add your test server ID (enable Discord Developer
   Mode, then right-click the server and copy its ID):

   ```dotenv
   CODQ_DISCORD_BOT_TOKEN=your_bot_token
   CODQ_DISCORD_TEST_GUILD_ID=your_test_server_id
   ```

   Do not paste the real token into a command, issue, or chat.
6. In PowerShell, run:

   ```powershell
   uv run codex-reset-tracker run-discord
   ```

   The test guild ID makes slash commands available in that server immediately;
   without it, commands are registered globally. Stop the process with `Ctrl+C`
   when finished.
7. In Discord, run `/set-alert-channel` in the test channel. Then run
   `/reset-bot-status` and `/test-reset-alert`. The latter posts one visibly
   synthetic, non-pinging message to the configured channel. Use
   `/preview-reset-alert` if you only want to see the embed privately.

The first tracker scan establishes a baseline and does not alert on old posts
by default. Use `/test-reset-alert` to verify message delivery instead of
waiting for a new public signal. Real X alerts require valid X authentication.
To receive a device notification, allow all messages for the test channel and
enable notifications in your Discord client.

## Accounts

The tracker has two safeguards:

1. Searches are generated as `from:<handle> reset`.
2. Every tweet is checked again locally; only authors in `polling.accounts` can
   alert.

That means broad or noisy search results from unrelated accounts are recorded as
`untrusted_author` and do not notify.

### Seeded Watchlist

The default watchlist includes official accounts and relevant people from
OpenAI, Anthropic/Claude and SpaceXAI/Grok.

| Group | Handles |
| --- | --- |
| OpenAI official | `@OpenAI`, `@OpenAIDevs`, `@ChatGPTapp`, `@OpenAIStatus` |
| OpenAI people | `@sama`, `@gdb`, `@markchen90`, `@nickaturley`, `@kevinweil` |
| OpenAI Codex | `@thsottiaux`, `@embirico`, `@hansonwng`, `@katyhshi` |
| Anthropic official | `@AnthropicAI`, `@claudeai`, `@ClaudeDevs` |
| Anthropic people | `@DarioAmodei`, `@DanielaAmodei`, `@jackclarkSF`, `@mikeyk`, `@ch402` |
| Claude Code | `@bcherny` |
| SpaceXAI and Grok | `@SpaceXAI`, `@grok`, `@bot` (Grok Bot) |
| Grok people | `@elonmusk` |

Sources used to seed this list include official X pages and public index pages
for [OpenAI Developers](https://x.com/OpenAIDevs),
[Tibo / Codex](https://x.com/thsottiaux/with_replies?lang=en),
[Anthropic](https://x.com/AnthropicAI/status/2025997928242811253?lang=en),
[Claude](https://x.com/claudeai/status/1972706815885373936), the reported
[@ClaudeDevs launch](https://awesomeagents.ai/news/anthropic-claudedevs-x-account-launch/),
and public profiles for [Boris Cherny](https://x.com/bcherny/status/2015524460481388760)
and the [Anthropic radar](https://llmgram.app/anthropic-radar/).
The Grok watchlist is informed by [SpaceXAI's official account links](https://x.ai/contact)
and [whenreset.dev's Grok source list](https://whenreset.dev/grok).
For broad accounts such as `@elonmusk` and `@SpaceXAI`, a Grok product cue and
a usage/limit cue are required in addition to the reset keyword. Grok Bot alerts
are labeled separately because its allowance is separate from Grok chat.
Existing `config.json` files keep their account choices; run
`uv run codex-reset-tracker accounts defaults` to add the new recommendations.

Reset posts are potential signals, not confirmation that a particular account's
quota changed. Banked resets and reset tokens may require redemption; read the
linked original post and check the product's own usage page.

## Timezones

| Timezone | Purpose | Default |
| --- | --- | --- |
| User timezone | where alert windows are shown | `auto` |
| Source timezone | how tweet phrases are interpreted | per account |

Example: if `@thsottiaux` says `this evening`, the phrase is interpreted in
`America/Los_Angeles`, then translated to your detected local timezone.

Override your timezone only when needed:

```json
{
  "local_timezone": "Asia/Saigon",
  "time": {
    "user_timezone": "Asia/Saigon"
  }
}
```

## Background Service

Use the service for normal background operation:

```bash
uv run codex-reset-tracker service install
uv run codex-reset-tracker service start
uv run codex-reset-tracker service status
uv run codex-reset-tracker service logs
```

Use this for a normal Linux or WSL install. It runs through `systemd --user`,
gets restart handling, and writes logs to the user journal.

For one-off testing, run it in the foreground:

```bash
uv run codex-reset-tracker run
uv run codex-reset-tracker status
```

### Optional WSL Auto-Start

If you use WSL and want tracker auto-start after Windows logon/unlock/wake,
install the Windows scheduled-task bridge:

```bash
uv run codex-reset-tracker service install
uv run codex-reset-tracker service start
uv run codex-reset-tracker windows-startup install --force
uv run codex-reset-tracker windows-startup status
```

The scheduled task wakes WSL and starts the `service` mode. It does not use the
portable daemon path.

If distro detection fails, set it explicitly:

```bash
uv run codex-reset-tracker windows-startup install --distro Ubuntu --force
```

Microsoft documents that [`wsl.exe` can run a specific distro from Windows](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)
and that [WSL supports `systemd`](https://learn.microsoft.com/en-us/windows/wsl/systemd);
this project uses both pieces for the Windows Scheduled Task bridge.

### Daemon Fallback

Use this only if `service install` fails because `systemd --user` is unavailable:

```bash
uv run codex-reset-tracker daemon start
uv run codex-reset-tracker daemon status
uv run codex-reset-tracker daemon logs
```

The daemon is just a detached local process with a pid file and log file under
`data/runtime`. It is not an installed OS service and should not be run at the
same time as `service`.

## Diagnostics

Historical diagnostic scan, without touching production state or sending real
notifications:

```bash
uv run codex-reset-tracker debug-scan \
  --config config.json \
  --query 'from:thsottiaux reset' \
  --dump-stream data/runtime/debug-scan.jsonl
```

Use a specific account override:

```bash
uv run codex-reset-tracker debug-scan --account thsottiaux
```

Run tests:

```bash
uv run ruff check .
uv run python -m unittest discover -s tests
```

## Runtime Notes

| Topic | Detail |
| --- | --- |
| Fresh tweets | first-ever scan baselines visible tweets; restarts catch up since the last scan, capped at 24 hours |
| Rate limits | default polling is 20 minutes plus jitter |
| Twikit patches | compatibility monkeypatch registry lives in `src/codex_reset_tracker/twikit_compat.py` |
| State | SQLite tracks seen tweet ids and alerted text hashes |
| Secrets | `.env`, `data/`, cookies, and local DBs are git-ignored |
