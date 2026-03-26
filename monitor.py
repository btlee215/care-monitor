import argparse
import os
import sys
import time
from datetime import datetime, timezone

import praw
import yaml

from db import Database
from notifier import Notifier
from scorer import Scorer


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def build_reddit(config: dict) -> praw.Reddit:
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "care-monitor/1.0"),
    )


def all_subreddits(config: dict) -> list:
    result = []
    for tier_key, subs in config.get("subreddits", {}).items():
        tier_num = int(tier_key.replace("tier", ""))
        for sub in subs:
            result.append((sub, tier_num))
    return result


def run_once(config, reddit, scorer, notifier, db):
    settings = config.get("settings", {})
    lookback_hours = settings.get("lookback_hours", 4)
    posts_per_sub = settings.get("posts_per_subreddit", 100)
    silence_days = settings.get("silence_alert_days", 7)

    cutoff = datetime.now(tz=timezone.utc).timestamp() - lookback_hours * 3600

    total_scanned = 0
    total_found = 0
    skipped_subs = 0

    for sub_name, _tier in all_subreddits(config):
        try:
            subreddit = reddit.subreddit(sub_name)
            had_match = False
            for post in subreddit.new(limit=posts_per_sub):
                if post.created_utc < cutoff:
                    continue
                total_scanned += 1
                if db.is_seen(post.id):
                    continue
                result = scorer.evaluate(post)
                if result:
                    db.record_surfaced(result)
                    notifier.send(result)
                    had_match = True
                    total_found += 1
            db.update_subreddit_checked(sub_name, had_match)
        except Exception as e:
            print(f"[monitor] Skipping r/{sub_name}: {e}")
            skipped_subs += 1

    for sub in db.get_silent_subreddits(silence_days):
        notifier.send_silence_alert(sub, silence_days)

    notifier.send_run_summary(total_found, total_scanned, skipped_subs)


def main():
    parser = argparse.ArgumentParser(description="Care Monitor")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval-hours", type=float, default=None)
    parser.add_argument("--log-engagement", action="store_true")
    parser.add_argument("--show-engagements", action="store_true")
    args = parser.parse_args()

    if not os.environ.get("REDDIT_CLIENT_ID") or not os.environ.get("REDDIT_CLIENT_SECRET"):
        print("ERROR: REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env vars are required.")
        sys.exit(1)

    config = load_config(args.config)
    settings = config.get("settings", {})
    db = Database(settings.get("db_path", "data/monitor.db"))

    if args.show_engagements:
        for row in db.list_engagements():
            print(row)
        db.close()
        return

    if args.log_engagement:
        post_id = input("Post ID: ").strip()
        post_url = input("Post URL: ").strip()
        subreddit = input("Subreddit: ").strip()
        response_text = input("Response text: ").strip()
        notes = input("Notes: ").strip()
        db.log_engagement(post_id, post_url, subreddit, response_text, notes)
        print("Engagement logged.")
        db.close()
        return

    reddit = build_reddit(config)
    scorer = Scorer(config)
    notifier = Notifier(output_mode=settings.get("output_mode", "both"))

    interval = args.interval_hours or settings.get("lookback_hours", 4)

    if args.loop:
        while True:
            run_once(config, reddit, scorer, notifier, db)
            time.sleep(interval * 3600)
    else:
        run_once(config, reddit, scorer, notifier, db)

    db.close()


if __name__ == "__main__":
    main()
