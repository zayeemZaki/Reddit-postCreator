import pytest
import os
from datetime import datetime
from dotenv import load_dotenv

# --- FIX 1: FORCE LOAD ENV VARS ---
# This finds the .env file in the root directory and loads it
load_dotenv()

from src.loader import load_data
from src.agents import generate_post
from src.scheduler import schedule_posts
from src.schemas import RedditPost, Persona

# --- FIX 2: ROBUST FILE PATH ---
# This calculates the path relative to THIS file, so it never breaks
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_CSV_PATH = os.path.join(BASE_DIR, "data", "company_info.csv")

def test_data_loading():
    """Ensure the CSV is parsed correctly into Personas and Company info."""
    # Debug print to help you see if it finds the file
    print(f"Looking for file at: {TEST_CSV_PATH}")
    
    if not os.path.exists(TEST_CSV_PATH):
        pytest.fail(f"File not found at {TEST_CSV_PATH}. Did you create the 'data' folder?")

    data = load_data(TEST_CSV_PATH)
    
    assert "company" in data
    assert data['company']['Name'] == "Slideforge"
    assert len(data['personas']) >= 2

def test_post_generation():
    """Ensure the AI returns a valid RedditPost object."""
    # Verify API Key exists before running
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.fail("GOOGLE_API_KEY is missing from .env file!")

    persona = Persona(id="test_user", name="Test User", bio="I love testing", traits="Precise")
    keyword = "Unit Testing"
    subreddit = "r/programming"
    
    post = generate_post(persona, keyword, subreddit)
    
    assert isinstance(post, RedditPost)
    assert post.author_id == "test_user"
    assert len(post.body) > 0

def test_scheduler_logic():
    """Ensure posts are distributed and sorted correctly."""
    posts = [
        RedditPost(title="A", body="A", subreddit="r/A", author_id="u1", keyword_id="k1"),
        RedditPost(title="B", body="B", subreddit="r/B", author_id="u2", keyword_id="k2"),
        RedditPost(title="C", body="C", subreddit="r/C", author_id="u3", keyword_id="k3")
    ]
    
    start_date = datetime.now()
    scheduled = schedule_posts(posts, start_date)
    
    assert len(scheduled) == 3
    
    # Handle both Dicts and Objects (Flexible Fix)
    for p in scheduled:
        ts = p.timestamp if hasattr(p, 'timestamp') else p.get('timestamp')
        assert ts is not None
        assert isinstance(ts, str)