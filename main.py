from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests
import time
import html

app = FastAPI()
templates = Jinja2Templates(directory="templates")

HEADERS = {"User-Agent": "readonly-reddit-archive/1.0"}

# Simple in-memory cache
cache = {}
CACHE_TIME = 300  # seconds


def fetch_json(url):
    now = time.time()
    if url in cache:
        data, timestamp = cache[url]
        if now - timestamp < CACHE_TIME:
            return data
    r = requests.get(url, headers=HEADERS)
    data = r.json()
    cache[url] = (data, now)
    return data


# ---------------- HOME ----------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.html", {"request": request}
    )


# ---------------- SUBREDDIT ----------------
@app.get("/r/{subreddit}", response_class=HTMLResponse)
def subreddit_view(request: Request, subreddit: str, after: str = None):
    url = f"https://www.reddit.com/r/{subreddit}.json"
    if after:
        url += f"?after={after}"

    data = fetch_json(url)
    posts = []
    after_token = data["data"].get("after")  # move outside loop

    for post in data["data"]["children"]:
        p = post["data"]

        image_url = None
        if p.get("post_hint") == "image":
            image_url = p.get("url")
        elif "preview" in p:
            image_url = p["preview"]["images"][0]["source"]["url"]

        if image_url:
            image_url = html.unescape(image_url)

        posts.append({
            "id": p["id"],
            "title": p["title"],
            "author": p["author"],
            "score": p["score"],
            "comments": p["num_comments"],
            "image": image_url
        })

    return templates.TemplateResponse(
        "subreddit.html",
        {
            "request": request,
            "subreddit": subreddit,
            "posts": posts,
            "after": after_token
        }
    )


# ---------------- POST ----------------
@app.get("/post/{post_id}", response_class=HTMLResponse)
def post_view(request: Request, post_id: str):
    url = f"https://www.reddit.com/comments/{post_id}.json"
    data = fetch_json(url)

    post_data = data[0]["data"]["children"][0]["data"]
    comments_raw = data[1]["data"]["children"]

    image_url = None
    if post_data.get("post_hint") == "image":
        image_url = post_data.get("url")
    elif "preview" in post_data:
        image_url = post_data["preview"]["images"][0]["source"]["url"]

    if image_url:
        image_url = html.unescape(image_url)

    def parse_comments(comments):
        parsed = []
        for c in comments:
            if c["kind"] != "t1":
                continue
            d = c["data"]
            parsed.append({
                "author": d["author"],
                "body": d["body"],
                "replies": parse_comments(d["replies"]["data"]["children"])
                if d.get("replies") else []
            })
        return parsed

    comments = parse_comments(comments_raw)

    return templates.TemplateResponse(
        "post.html",
        {
            "request": request,
            "post": post_data,
            "comments": comments,
            "image": image_url
        }
    )


# ---------------- USER PROFILE ----------------
@app.get("/u/{username}", response_class=HTMLResponse)
def user_view(request: Request, username: str):
    about_url = f"https://www.reddit.com/user/{username}/about.json"
    posts_url = f"https://www.reddit.com/user/{username}/submitted.json"
    comments_url = f"https://www.reddit.com/user/{username}/comments.json"

    about = fetch_json(about_url)
    posts_data = fetch_json(posts_url)
    comments_data = fetch_json(comments_url)

    user = about["data"]

    posts = []
    for p in posts_data["data"]["children"]:
        d = p["data"]
        posts.append({
            "id": d["id"],
            "title": d["title"],
            "subreddit": d["subreddit"],
            "score": d["score"]
        })

    comments = []
    for c in comments_data["data"]["children"]:
        d = c["data"]
        comments.append({
            "body": d["body"],
            "subreddit": d["subreddit"],
            "score": d["score"]
        })

    return templates.TemplateResponse(
        "user.html",
        {
            "request": request,
            "user": user,
            "posts": posts,
            "comments": comments
        }
    )
