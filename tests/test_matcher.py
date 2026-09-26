import unittest

from codex_reset_tracker.config import MatchingConfig
from codex_reset_tracker.matcher import RegexMatcher
from codex_reset_tracker.models import TweetRecord


def tweet(text: str, author: str = "sama") -> TweetRecord:
    return TweetRecord(
        id="1",
        author_username=author,
        author_name=author,
        text=text,
        created_at=None,
        url=f"https://x.com/{author}/status/1",
        source="test",
    )


class RegexMatcherTests(unittest.TestCase):
    def test_matches_any_reset_keyword(self):
        matcher = RegexMatcher(MatchingConfig())

        result = matcher.match(tweet("Seeing some issues with propagation of resets on some accounts, team is looking. Stay tuned."))

        self.assertIsNotNone(result)
        self.assertIn("propagation of resets", result.excerpt)

    def test_matches_resetting_limits_from_trusted_account_context(self):
        matcher = RegexMatcher(MatchingConfig())

        result = matcher.match(tweet(
            "Five million users would agree. Resetting the limits tomorrow morning to celebrate.\n\n"
            "Time to go /fast"
        ))

        self.assertIsNotNone(result)
        self.assertIn("Resetting the limits", result.excerpt)

    def test_rejects_unrelated_reset(self):
        matcher = RegexMatcher(MatchingConfig())

        result = matcher.match(tweet("Please reset your password if you lost access to your account."))

        self.assertIsNone(result)

    def test_requires_all_default_contexts(self):
        matcher = RegexMatcher(MatchingConfig())

        result = matcher.match(tweet("Codex had a great week."))

        self.assertIsNone(result)

    def test_any_mode_can_match_single_pattern(self):
        matcher = RegexMatcher(
            MatchingConfig(
                require_all_include_patterns=False,
                include_patterns=(r"\breset\s+quota\b",),
                exclude_patterns=(),
            )
        )

        result = matcher.match(tweet("Looks like reset quota messaging is live."))

        self.assertIsNotNone(result)

    def test_elon_grok_quota_signal_requires_product_and_limit_context(self):
        matcher = RegexMatcher(MatchingConfig())

        self.assertIsNotNone(
            matcher.match(tweet("We will reset Grok usage limits this week.", "elonmusk"))
        )
        self.assertIsNone(matcher.match(tweet("Reset the launch countdown.", "elonmusk")))
        self.assertIsNone(matcher.match(tweet("We reset the launch limit.", "elonmusk")))
        self.assertIsNone(matcher.match(tweet("Reset Grok's design theme.", "elonmusk")))

    def test_grok_bot_limit_reset_matches_without_product_word_in_post(self):
        matcher = RegexMatcher(MatchingConfig())

        result = matcher.match(tweet("Weekly limits have been reset for all users.", "bot"))

        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
