"""X official archive search adapter. Access depends on the user's API entitlement."""

from datetime import datetime, timezone
import requests
from opinion_gateway.credentials import get
from opinion_gateway.connectors import WaitingForAuthentication


def fetch_page(payload):
    token = get("X_BEARER_TOKEN")
    if not token:
        raise WaitingForAuthentication("X archive search needs a local bearer token")
    event = payload["event"]
    if not event.get("start") or not event.get("end"):
        raise ValueError("X archive search requires an explicit time interval")
    terms = [
        '"' + k.replace('"', " ").replace("\\", " ").strip() + '"'
        for k in event["keywords"]
        if k.strip()
    ]
    query = " OR ".join(terms)
    if not payload.get("include_comments"):
        query = "(" + query + ") -is:reply"
    elif not payload.get("include_posts", True):
        query = "(" + query + ") is:reply"
    params = {
        "query": query,
        "start_time": event["start"],
        "end_time": event["end"],
        "max_results": min(
            100, max(10, payload["remaining_posts"] + payload["remaining_comments"])
        ),
        "post.fields": "created_at,conversation_id,public_metrics,geo,text",
        "expansions": "geo.place_id,author_id,referenced_posts",
        "place.fields": "full_name,country",
    }
    if payload.get("cursor"):
        params["next_token"] = payload["cursor"]
    response = requests.get(
        "https://api.x.com/2/tweets/search/all",
        params=params,
        headers={"Authorization": "Bearer " + token},
        timeout=(10, 40),
        allow_redirects=False,
    )
    if response.status_code in (401, 403):
        raise WaitingForAuthentication(
            "X credential or archive-search entitlement unavailable"
        )
    if response.status_code != 200:
        raise RuntimeError(f"X search HTTP {response.status_code}")
    data = response.json()
    if data.get("errors") and not data.get("data"):
        raise RuntimeError("X search returned API errors")
    places = {
        p["id"]: p.get("full_name", p.get("country"))
        for p in data.get("includes", {}).get("places", [])
    }
    records = []
    now = datetime.now(timezone.utc).isoformat()
    for row in data.get("data", []):
        refs = row.get("referenced_tweets", row.get("referenced_posts", []))
        parent = next((r["id"] for r in refs if r["type"] == "replied_to"), None)
        metrics = row.get("public_metrics", {})
        records.append(
            {
                "platform": "x",
                "raw_id": row["id"],
                "kind": "comment" if parent else "post",
                "parent_ref": parent,
                "thread_ref": row.get("conversation_id"),
                "content": row.get("text", ""),
                "published_at": row.get("created_at"),
                "time_status": "parsed" if row.get("created_at") else "missing",
                "collected_at": now,
                "author_ref": row.get("author_id"),
                "source_url": "https://x.com/i/status/" + row["id"],
                "region": places.get(row.get("geo", {}).get("place_id")),
                "read_count": metrics.get("impression_count"),
                "like_count": metrics.get("like_count"),
                "comment_count": metrics.get("reply_count"),
                "repost_count": metrics.get(
                    "retweet_count", metrics.get("repost_count")
                ),
            }
        )
    return {
        "records": records,
        "next_cursor": data.get("meta", {}).get("next_token"),
        "partial": bool(data.get("errors")),
    }
