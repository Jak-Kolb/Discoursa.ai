import os
import time
import json
import logging
import tweepy
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
from .db import SessionLocal
from .models import User, DebateRoot, DebateBranch, BotState
from .llm import DebateLLM, LLMMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_fernet():
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY not set")
    return Fernet(key.encode() if isinstance(key, str) else key)

def get_twitter_client():
    return tweepy.Client(
        bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
        consumer_key=os.getenv("TWITTER_API_KEY"),
        consumer_secret=os.getenv("TWITTER_API_SECRET"),
        access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
        access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
        wait_on_rate_limit=True
    )

def get_since_id(db: Session):
    state = db.query(BotState).filter(BotState.key == "since_id").first()
    return state.value if state else None

def save_since_id(db: Session, since_id):
    state = db.query(BotState).filter(BotState.key == "since_id").first()
    if not state:
        state = BotState(key="since_id", value=str(since_id))
        db.add(state)
    else:
        state.value = str(since_id)
    db.commit()

def check_rate_limit(db: Session, user_id: str) -> bool:
    """
    Check if user has exceeded debate limit (e.g. 5 per hour).
    Returns True if allowed, False if limited.
    """
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    count = db.query(DebateBranch).filter(
        DebateBranch.challenger_id == user_id,
        DebateBranch.created_at > one_hour_ago
    ).count()
    return count < 5

def process_mentions():
    client = get_twitter_client()
    db = SessionLocal()
    
    try:
        since_id = get_since_id(db)
        me = client.get_me().data
        my_id = me.id
        
        response = client.get_users_mentions(
            id=my_id,
            since_id=since_id,
            expansions=["author_id", "referenced_tweets.id"],
            tweet_fields=["created_at", "conversation_id", "text"]
        )
        
        if not response.data:
            return

        new_since_id = response.meta.get("newest_id")
        if new_since_id:
            save_since_id(db, new_since_id)

        referenced_tweets = {t.id: t for t in response.includes.get("tweets", [])} if response.includes else {}

        for tweet in reversed(response.data):
            if str(tweet.author_id) == str(my_id):
                continue # Ignore self
            
            process_tweet(client, db, tweet, referenced_tweets, my_id)
            
    except Exception as e:
        logger.error(f"Error in process_mentions: {e}")
    finally:
        db.close()

def process_tweet(client, db: Session, tweet, referenced_tweets, bot_id):
    text = tweet.text.lower()
    author_id = str(tweet.author_id)
    
    # Case A: New Debate ("Debate this")
    if "debate this" in text:
        handle_new_debate(client, db, tweet, referenced_tweets, author_id)
    else:
        # Case B: Continuation (Reply to Bot)
        # We need to check if this tweet is a reply to the bot
        refs = tweet.referenced_tweets
        if refs:
            replied_to = next((r for r in refs if r.type == "replied_to"), None)
            if replied_to:
                # Check if the tweet replied to was by the bot? 
                # We don't have the author of the referenced tweet easily unless we fetch it.
                # But we can check if the replied_to_id matches a last_tweet_id in our DB.
                handle_continuation(client, db, tweet, replied_to.id, author_id)

def handle_new_debate(client, db: Session, tweet, referenced_tweets, challenger_id):
    # Rate Limit Check
    if not check_rate_limit(db, challenger_id):
        try:
            client.create_tweet(text="You have reached your debate limit for the hour.", in_reply_to_tweet_id=tweet.id)
        except:
            pass
        return

    # Find the Parent Tweet (The OP)
    refs = tweet.referenced_tweets
    if not refs:
        return

    parent_ref = next((r for r in refs if r.type == "replied_to" or r.type == "quoted"), None)
    if not parent_ref:
        return

    parent_tweet = referenced_tweets.get(parent_ref.id)
    if not parent_tweet:
        try:
            parent_tweet = client.get_tweet(parent_ref.id, expansions=["author_id"]).data
        except:
            return

    # Check User Auth
    user = db.query(User).filter(User.id == challenger_id).first()
    if not user:
        try:
            client.create_tweet(
                text="Please link your account at [Discoursa URL] to start debates.",
                in_reply_to_tweet_id=tweet.id
            )
        except:
            pass
        return

    # Decrypt Key
    try:
        fernet = get_fernet()
        api_key = fernet.decrypt(user.encrypted_api_key.encode()).decode()
    except:
        return

    # Create DebateRoot if not exists
    root = db.query(DebateRoot).filter(DebateRoot.id == str(parent_tweet.id)).first()
    if not root:
        root = DebateRoot(
            id=str(parent_tweet.id),
            topic=parent_tweet.text,
            op_handle=str(parent_tweet.author_id) # Ideally fetch handle, but ID is okay for now
        )
        db.add(root)
        db.commit()

    # Generate Argument
    llm = DebateLLM(api_key=api_key)
    opening_arg = llm.generate_tweet_reply([], parent_tweet.text)

    # Reply to User A (The Challenger), quoting the OP
    try:
        response = client.create_tweet(
            text=opening_arg,
            in_reply_to_tweet_id=tweet.id,
            quote_tweet_id=parent_tweet.id
        )
        bot_tweet_id = response.data["id"]

        # Create DebateBranch
        branch = DebateBranch(
            root_id=root.id,
            challenger_id=challenger_id,
            last_tweet_id=str(bot_tweet_id),
            history=[
                {"role": "user", "content": f"Debate this: {parent_tweet.text}"},
                {"role": "assistant", "content": opening_arg}
            ]
        )
        db.add(branch)
        db.commit()
    except Exception as e:
        logger.error(f"Error creating debate branch: {e}")

def handle_continuation(client, db: Session, tweet, replied_to_id, author_id):
    # Find the branch where last_tweet_id matches replied_to_id
    branch = db.query(DebateBranch).filter(DebateBranch.last_tweet_id == str(replied_to_id)).first()
    
    if not branch:
        return # Not a reply to a known debate thread

    # Verify the user is the challenger?
    # The prompt says "User A replies to the Bot's tweet". 
    # Ideally we only debate the challenger in this branch.
    if branch.challenger_id != author_id:
        return # Ignore interlopers for now

    # Get User Key
    user = db.query(User).filter(User.id == author_id).first()
    if not user:
        return
    
    try:
        fernet = get_fernet()
        api_key = fernet.decrypt(user.encrypted_api_key.encode()).decode()
    except:
        return

    # Update History
    history = list(branch.history) # Copy
    history.append({"role": "user", "content": tweet.text})
    
    # Generate Rebuttal
    llm = DebateLLM(api_key=api_key)
    llm_history = [LLMMessage(role=m["role"], content=m["content"]) for m in history]
    
    # RAG placeholder: if len(history) > 3: retrieve context...
    
    rebuttal = llm.generate_tweet_reply(llm_history, "")

    try:
        response = client.create_tweet(
            text=rebuttal,
            in_reply_to_tweet_id=tweet.id
        )
        bot_tweet_id = response.data["id"]

        # Update Branch
        history.append({"role": "assistant", "content": rebuttal})
        branch.history = history
        branch.last_tweet_id = str(bot_tweet_id)
        db.commit()
    except Exception as e:
        logger.error(f"Error replying to continuation: {e}")

if __name__ == "__main__":
    while True:
        process_mentions()
        time.sleep(60)
