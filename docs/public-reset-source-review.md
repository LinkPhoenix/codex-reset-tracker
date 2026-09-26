# Public reset tracker review

Reviewed on 2026-09-26. These sites provide public observations and product ideas; their source code was not needed or copied.

| Site | Useful public information | Existing alert delivery |
| --- | --- | --- |
| [codex-reset.com release notes](https://codex-reset.com/codexreset-release) | Separates strong Tibo hints, announced global resets, and banked reset lifecycle updates. Its timeline treats banked credits separately from immediate usage resets. | Discord community channel, Telegram, email, and browser push. |
| [whenreset.dev](https://whenreset.dev/) | Tracks Codex, Claude, and Grok with links to original X posts, affected audience, reset type, and history. Its Grok page separates Grok Bot limits from Grok chat. | Browser alerts, Telegram, and Slack/Discord webhooks. |

The focused default watchlist uses `@thsottiaux` for Codex, `@ClaudeDevs` for Claude, and `@grok`, `@bot`, `@elonmusk`, and `@SpaceXAI` for Grok. The first five match the [WhenReset homepage's listed public-post sources](https://whenreset.dev/); its [Grok page](https://whenreset.dev/grok) also identifies `@SpaceXAI`. [Codex Reset's Tibo radar](https://codex-reset.com/tibo) corroborates the Codex source. Previous recommended accounts remain recognizable for users who explicitly keep them, but new setups do not poll them. Existing installations can run `codex-reset-tracker accounts focus` to remove retired defaults and preserve other custom accounts.

The bot labels Grok Bot separately and filters broad Elon Musk and SpaceXAI posts for both Grok and quota context. The message says **potential signal** because a post alone cannot verify each user's account state. A banked reset or reset token gets a distinct label. This is a local interpretation of public posts, not a copy of either site's classifier or event database.

`codex-reset.com` also offers a [documented public JSON API](https://codex-reset.com/developers). If a future version reads and relays its data, the site's published terms require a project-identifying User-Agent and a linked `Data: codex-reset.com` credit on every bot message displaying that data. Its API guidance says to poll no more than once a minute, honor `Retry-After`, and rely only on documented fields. The current bot does not consume that API. It retains the original X post as the alert source.

Sources: [codex-reset.com release notes](https://codex-reset.com/codexreset-release), [API contract](https://codex-reset.com/developers), [terms](https://codex-reset.com/terms), [whenreset.dev homepage](https://whenreset.dev/), [Grok records and scope notes](https://whenreset.dev/grok), and [SpaceXAI's official X account links](https://x.ai/contact).
