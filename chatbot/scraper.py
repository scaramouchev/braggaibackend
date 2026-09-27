import bs4,requests,time
from datetime import datetime, timedelta, timezone
from sentence_transformers import SentenceTransformer
from supabase import create_client
from urllib.parse import urljoin
import hashlib

supabase = create_client(
    "https://abmrujvzncbhftliwztj.supabase.co",
    "sb_secret_fBfMmnQ2TVCqXNVvOSlOQQ_mUQDq7c_"
)

seen_urls = set()
model = SentenceTransformer("all-MiniLM-L6-v2")
def chunk_text(text, chunk_size=500):
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i + chunk_size]))

    return chunks

def ingest_page(title, source_url, text):
    content_hash = hashlib.sha256(text.encode()).hexdigest()

    existing = supabase.table("documents") \
        .select("content_hash") \
        .eq("source_url", source_url) \
        .limit(1) \
        .execute()

    if existing.data and existing.data[0]["content_hash"] == content_hash:
        print("Unchanged, skipping:", source_url)
        return

    if existing.data:
        print("Changed, updating:", source_url)

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

def ingest_tweet(tweet, username):
    text = tweet["text"]
    tweet_id = tweet["id"]

    source_url = f"https://x.com/{username}/status/{tweet_id}"

    ingest_page(
        title=f"X post by @{username}",
        source_url=source_url,
        text=text
    )

session = requests.Session()
response = session.get("https://famu.edu")
scraper = bs4.BeautifulSoup(response.content,'html.parser')
lis = scraper.select('li[class="nav-accordion__item"]')
socials = scraper.select('ul[class="social"] li a[href]')
API_KEY = "new1_0d7d8081e97c44ecb8c8d14fa235288d"
INSTA_API_KEY = "4d110e8a-f86e-4328-9174-b50c8c9a50de"
headers = {
    "x-api-key": API_KEY
}
LAST_CHECKED_TIME = datetime.now(timezone.utc) - timedelta(hours=48)


#not my code, modified to fit our requirements
def check_for_new_tweets(TARGET_ACCOUNT):
    global LAST_CHECKED_TIME

    # Compute the time window. The advanced_search endpoint takes only
    # `query` and `queryType`; time bounds are advanced-search operators
    # (since_time: / until_time:, Unix seconds) embedded in the query string.
    until_time = datetime.now(timezone.utc)
    since_time = LAST_CHECKED_TIME

    #if until_time - LAST_CHECKED_TIME < timedelta(hours=24):
        #do something here
        #return

    # Construct the query — time bounds go inline as advanced-search operators.
    query = (
        f"from:{TARGET_ACCOUNT} include:nativeretweets "
        f"since_time:{int(since_time.timestamp())} until_time:{int(until_time.timestamp())}"
    )
    # Please refer to this document for detailed advanced search syntax.
    # https://github.com/igorbrigadir/twitter-advanced-search

    # API endpoint
    url = "https://api.twitterapi.io/twitter/tweet/advanced_search"

    # Request parameters
    params = {
        "query": query,
        "queryType": "Latest",
    }

    # Headers with API key
    headers = {
        "X-API-Key": API_KEY
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
            break

        else:
            print(f"Error: {response.status_code} - {response.text}")
            break

    # Process all collected tweets
    if all_tweets:
        print(f"Found {len(all_tweets)} total tweets from {TARGET_ACCOUNT}!")
        for tweet in all_tweets:
            print(f"[{tweet['createdAt']}] {tweet['text']}")
            ingest_tweet(tweet, TARGET_ACCOUNT)
    else:
        print(f"No new tweets from {TARGET_ACCOUNT} since last check.")

    # Update the last checked time
    LAST_CHECKED_TIME = until_time

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

for li in lis:
    title = li.find("span", class_=False).get_text(strip=True)
    print(title)

    for link in li.select("a[href]"):

        source_url = urljoin("https://famu.edu", link["href"])

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

        ingest_page(title,source_url,text)



        print(link["href"])



print("Socials:")

instagram = "hello"
facebook = "hello"
x = "hello"
tiktok = "hello"

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









