import bs4,requests,time
from datetime import datetime, timedelta, timezone
from sentence_transformers import SentenceTransformer
from urllib.parse import urljoin
import hashlib
import os
from supabase_client import supabase
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

X_API_KEY = os.environ.get("X_API_KEY")
INSTA_API_KEY = os.environ.get("INSTA_API_KEY")

status = supabase.table("scraper_status") \
    .select("last_checked_time") \
    .eq("id", 1) \
    .single() \
    .execute()

LAST_CHECKED_TIME = datetime.fromisoformat(
    status.data["last_checked_time"].replace("Z", "+00:00")
)

model = SentenceTransformer("all-MiniLM-L6-v2")

def chunk_text(text, chunk_size=500):
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i + chunk_size]))

    return chunks

def ingest_page(title, source_url, text, model):
    content_hash = hashlib.sha256(text.encode()).hexdigest()

    existing = supabase.table("documents") \
        .select("content_hash") \
        .eq("source_url", source_url) \
        .limit(1) \
        .execute()

    if existing.data and existing.data[0]["content_hash"] == content_hash:
        return

    if existing.data:
        supabase.table("documents") \
            .delete() \
            .eq("source_url", source_url) \
            .execute()

    chunks = chunk_text(text)

    for chunk in chunks:
        embedding = model.encode(chunk).tolist()

        supabase.table("documents").insert({
            "content": chunk,
            "title": title,
            "source_url": source_url,
            "content_hash": content_hash,
            "embedding": embedding
        }).execute()

def ingest_socials(socials, model):
    lines = []
    seen = set()

    for s in socials:
        href = urljoin("https://famu.edu", s["href"])
        if href in seen:
            continue
        seen.add(href)

        platform = urlparse(href).netloc.replace("www.", "")
        lines.append(f"- {platform}: {href}")

    if not lines:
        return

    text = (
        "FAMU official social media accounts. "
        "Follow Florida A&M University (FAMU) on social media:\n"
        + "\n".join(lines)
    )

    ingest_page(
        title="FAMU Social Media",
        source_url="https://famu.edu/#social-links",
        text=text,
        model=model
    )

def ingest_tweet(tweet, username, model):
    text = tweet["text"]
    tweet_id = tweet["id"]

    source_url = f"https://x.com/{username}/status/{tweet_id}"

    ingest_page(
        title=f"X post by @{username}",
        source_url=source_url,
        text=text,
        model=model
    )

#not my code, modified to fit our requirements
def check_for_new_tweets(TARGET_ACCOUNT):
    global LAST_CHECKED_TIME

    # Compute the time window. The advanced_search endpoint takes only
    # `query` and `queryType`; time bounds are advanced-search operators
    # (since_time: / until_time:, Unix seconds) embedded in the query string.
    until_time = datetime.now(timezone.utc)
    since_time = LAST_CHECKED_TIME

    # Construct the query — time bounds go inline as advanced-search operators.
    query = (
        f"from:{TARGET_ACCOUNT} include:nativeretweets "
        f"since_time:{int(since_time.timestamp())} until_time:{int(until_time.timestamp())}"
    )

    url = "https://api.twitterapi.io/twitter/tweet/advanced_search"

    # Request parameters
    params = {
        "query": query,
        "queryType": "Latest",
    }

    # Headers with API key
    headers = {
        "X-API-Key": X_API_KEY
    }

    # Make the request and handle pagination
    all_tweets = []
    next_cursor = None

    while True:
        # Add cursor to params if we have one
        if next_cursor:
            params["cursor"] = next_cursor

        response = requests.get(url, headers=headers, params=params)

        # Parse the response
        if response.status_code == 200:
            data = response.json()
            tweets = data.get("tweets", [])

            if tweets:
                all_tweets.extend(tweets)

            # Check if there are more pages
            if data.get("has_next_page", False) and data.get("next_cursor", "") != "":
                next_cursor = data.get("next_cursor")
                continue
            else:
                break
        elif response.status_code == 429:
            return

        else:
            return

    # Process all collected tweets
    if all_tweets:
        for tweet in all_tweets:
            ingest_tweet(tweet, TARGET_ACCOUNT, model)
        

    LAST_CHECKED_TIME = until_time

    supabase.table("scraper_status").update(
        {"last_checked_time": until_time.isoformat()}
    ).eq("id", 1).execute()

def checkinstagram(HANDLE):
    response = requests.get(
        "https://api.hasdata.com/scrape/instagram/posts",
        params={
            "handle": HANDLE,
            "limit": 12
        },
        headers={
            "x-api-key": INSTA_API_KEY
        }
    )

    print(response.json())


def scrape():
    seen_urls = set()
    session = requests.Session()
    response = session.get("https://famu.edu")
    scraper = bs4.BeautifulSoup(response.content,'html.parser')
    lis = scraper.select('li[class="nav-accordion__item"]')
    socials = scraper.select('ul[class="social"] li a[href]')

    for li in lis:
        title = li.find("span", class_=False).get_text(strip=True)
        print(title)

        for link in li.select("a[href]"):

            source_url = urljoin("https://famu.edu", link["href"]).split("#")[0].rstrip("/")

            if source_url in seen_urls:
                continue

            seen_urls.add(source_url)
            try:
                print("Fetching:", source_url, flush=True)

                tempresponse = session.get(
                    source_url,
                    timeout=(5, 10)
                )

                tempresponse.raise_for_status()

                tempscraper = bs4.BeautifulSoup(tempresponse.content, 'html.parser')

                for element in tempscraper.select("nav, header, footer, script, style"):
                    element.decompose()

                text = tempscraper.get_text(" ", strip=True)

                print("Fetched:", source_url, flush=True)

            except requests.RequestException as e:
                print(f"FAILED: {source_url}", flush=True)
                print(f"Reason: {e}", flush=True)
                continue

            ingest_page(title,source_url,text,model)



            print(link["href"])



    ingest_socials(socials, model)

    for social in socials:
        url = social["href"]
        print(url)
        if "x.com/" in url:
            username = url.split('/')[3]
            check_for_new_tweets(username)
        #elif "instagram.com/" in url:
            #username = url.split('/')[3]
            #checkinstagram(username)
        else:
            continue









