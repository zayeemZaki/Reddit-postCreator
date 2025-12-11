from typing import List, Optional

from pydantic import BaseModel


class Persona(BaseModel):
    """Represents a Reddit user persona with identity and personality traits."""
    
    id: str
    name: str
    bio: str
    traits: str


class RedditPost(BaseModel):
    """Represents a Reddit post with content and metadata."""
    
    title: str
    body: str
    subreddit: str
    author_id: str
    keyword_id: str
    timestamp: Optional[str] = None


class RedditComment(BaseModel):
    """Represents a Reddit comment with text and parent relationships."""
    
    text: str
    author_id: str
    parent_id: Optional[str] = None
    parent_comment_id: Optional[str] = None
    timestamp: Optional[str] = None


class WeekPlan(BaseModel):
    """Represents a weekly schedule of Reddit posts."""
    
    posts: List[RedditPost]