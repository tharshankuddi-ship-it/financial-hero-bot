"""
trend_engine.py - Fetches trending topics from Reddit
"""
import requests
import random

SUBREDDITS = ["todayilearned", "space", "science", "history", "psychology", "economics"]

def get_trending_topic() -> str:
    """Fetch a trending post title from Reddit and convert it to a topic."""
    try:
        subreddit = random.choice(SUBREDDITS)
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=10"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        posts = response.json()["data"]["children"]
        # Pick a random post from top 10
        post = random.choice(posts)["data"]["title"]
        print(f"Trending topic found: {post}")
        return post
    except Exception as e:
        print(f"Reddit fetch failed ({e}), using fallback topic")
        return "a surprising science fact"
