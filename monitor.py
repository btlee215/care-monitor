import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from types import SimpleNamespace

import yaml

from db import Database
from notifier import Notifier
from scorer import Scorer


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def all_subreddits(config: dict) -> list:
    result = []
    for tier_key, subs in config.get("subreddits", {}).items():
        tier_num = int(tier_key.replace("tier", ""))
        for sub in subs:
            result.append((sub, tier_num))
    return result


def _make_post(data: dict) -> SimpleNamespace:
    post = SimpleNamespace(**data)
    post.subreddit = SimpleNamespace(display_name=data.get("subreddit", ""))
    post.selftext = data.get("selftext", "")
    return post


def fetch_new_posts(sub_name: str, limit: int = 100) -> list:
    url = f"https://www.reddit.com/r/{sub_name}/new.json?limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "care-monitor/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return [_make_post(child["data"]) for child in body["data"]["children"]]
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f"[monitor] Rate limited on r/{sub_name}, waiting 60s and retrying...")
            time.sleep(60)
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return [_make_post(child["data"]) for child in body["data"]["children"]]
        raise


def run_once(config, scorer, notifier, db):
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
            posts = fetch_new_posts(sub_name, limit=posts_per_sub)
            had_match = False
            for post in posts:
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
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                print(f"[monitor] Skipping r/{sub_name}: HTTP {e.code} (private or banned)")
            else:
                print(f"[monitor] Skipping r/{sub_name}: HTTP {e.code}")
            skipped_subs += 1
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

    scorer = Scorer(config)
    notifier = Notifier(output_mode=settings.get("output_mode", "both"))

    interval = args.interval_hours or settings.get("lookback_hours", 4)

    if args.loop:
        while True:
            run_once(config, scorer, notifier, db)
            time.sleep(interval * 3600)
    else:
        run_once(config, scorer, notifier, db)

    db.close()


if __name__ == "__main__":
    main()
