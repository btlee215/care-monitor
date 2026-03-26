import json
import os
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from scorer import ScoredPost

SCORE_EMOJI = {5: "🚨", 4: "🔴", 3: "🟠", 2: "🟡"}


class Notifier:
    def __init__(self, webhook_url: Optional[str] = None, output_mode: str = "both"):
        self.webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
        self.output_mode = output_mode

    def send(self, post: ScoredPost):
        if self.output_mode in ("console", "both"):
            self._print_console(post)
        if self.output_mode in ("slack", "both"):
            self._post_slack(post)

    def _print_console(self, post: ScoredPost):
        emoji = SCORE_EMOJI.get(post.score, "⚪")
        ts = datetime.fromtimestamp(post.created_utc, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        snippet = post.body[:200].replace("\n", " ") if post.body else "(no body)"
        print(
            f"\n{emoji} Score {post.score} | r/{post.subreddit} (Tier {post.tier}) | {ts}\n"
            f"  Title: {post.title}\n"
            f"  Label: {post.priority_label}\n"
            f"  Reason: {post.reason}\n"
            f"  Snippet: {snippet}\n"
            f"  URL: {post.url}"
        )

    def _post_slack(self, post: ScoredPost):
        if not self.webhook_url:
            return
        emoji = SCORE_EMOJI.get(post.score, "⚪")
        ts = datetime.fromtimestamp(post.created_utc, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        snippet = post.body[:200].replace("\n", " ") if post.body else "(no body)"
        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} Score {post.score} — {post.priority_label}",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Subreddit:* r/{post.subreddit} (Tier {post.tier})"},
                        {"type": "mrkdwn", "text": f"*Posted:* {ts}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Title:* {post.title}"},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Reason:* {post.reason}"},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Snippet:* {snippet}"},
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View Post"},
                            "url": post.url,
                        }
                    ],
                },
            ]
        }
        self._http_post(payload)

    def send_silence_alert(self, subreddit: str, days: int):
        msg = f"⚠️ No matches from r/{subreddit} in {days}+ days."
        if self.output_mode in ("console", "both"):
            print(msg)
        if self.output_mode in ("slack", "both") and self.webhook_url:
            self._http_post({"text": msg})

    def send_run_summary(self, found: int, scanned: int, skipped_subs: int):
        msg = f"✅ Run complete — {found} matches found across {scanned} posts ({skipped_subs} subs skipped)."
        if self.output_mode in ("console", "both"):
            print(msg)
        if self.output_mode in ("slack", "both") and self.webhook_url:
            self._http_post({"text": msg})

    def _http_post(self, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
        except Exception as e:
            print(f"[Notifier] Slack post failed: {e}")
