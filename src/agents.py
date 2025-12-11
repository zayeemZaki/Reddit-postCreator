import json
import os
import random
import time
from typing import Dict, List

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from .schemas import Persona, RedditComment, RedditPost


def generate_with_retry(model: genai.GenerativeModel, prompt: str, max_retries: int = 3) -> genai.types.GenerateContentResponse:
    """Wrapper function to handle rate limiting with retry logic.
    
    Args:
        model: The GenerativeModel instance
        prompt: The prompt to send to the model
        max_retries: Maximum number of retry attempts (default: 3)
    
    Returns:
        The response from the model
    
    Raises:
        ResourceExhausted: If all retries fail
    """
    for attempt in range(max_retries):
        try:
            return model.generate_content(prompt)
        except google_exceptions.ResourceExhausted as e:
            if attempt < max_retries - 1:
                wait_time = 60
                print(f"Rate limit hit. Waiting {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"Failed after {max_retries} attempts.")
                raise


def generate_post(persona: Persona, keyword_text: str, subreddit: str, keyword_id: str) -> RedditPost:
    """Generate a Reddit post for a given persona about a specific keyword.

    Args:
        persona: The Persona object containing id, name, bio, and traits
        keyword_text: The human-readable keyword/topic text to write about
        subreddit: The target subreddit for the post
        keyword_id: The canonical keyword identifier to persist in outputs

    Returns:
        RedditPost object with title, body, subreddit, author_id, and keyword_id
    """
    # Configure Gemini API
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")

    genai.configure(api_key=api_key)

    # Build the system prompt
    system_prompt = f"""You are {persona.name}. 
        Your bio: {persona.bio}
        Your traits: {persona.traits}

        Write a Reddit post about "{keyword_text}" for the r/{subreddit} subreddit.
        The post should be authentic to your personality and traits.
        Keep the title concise and engaging.
        The body should be natural, conversational, and appropriate for Reddit.
        
        IMPORTANT FORMATTING RULES:
        - Do NOT include any salutations (e.g., 'Hey r/{subreddit}', 'Hello everyone'). Start the post directly with the content.
        - Avoid using Markdown formatting such as asterisks (*) or underscores (_) for emphasis within the body text.
        - Write in plain text with natural punctuation only.

        You must respond with valid JSON matching this schema:
        {{
            "title": "post title here",
            "body": "post body here",
            "subreddit": "{subreddit}",
            "author_id": "{persona.id}",
            "keyword_id": "{keyword_id}"
        }}"""

    # Create the model with JSON response format
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"},
    )

    # Generate the response with retry logic
    response = generate_with_retry(model, system_prompt)

    # Parse the JSON response with error handling
    try:
        post_data = json.loads(response.text)
    except json.JSONDecodeError as e:
        # Try to extract JSON from markdown code blocks if present
        text = response.text.strip()
        if text.startswith("```json") and text.endswith("```"):
            text = text[7:-3].strip()
            post_data = json.loads(text)
        elif text.startswith("```") and text.endswith("```"):
            text = text[3:-3].strip()
            post_data = json.loads(text)
        else:
            print(f"JSON Parse Error: {e}")
            print(f"Response text: {response.text[:500]}")
            raise

    # Create and return RedditPost object
    return RedditPost(**post_data)


def generate_comments(post: RedditPost, personas: List[Persona], limit: int = 2) -> List[RedditComment]:
    """Generate up to `limit` Reddit comments for a post from other personas.

    Args:
        post: The RedditPost object to generate comments for
        personas: List of all available Persona objects
        limit: Maximum number of comments to generate (defaults to 2)

    Returns:
        List of RedditComment objects from selected personas
    """
    # Configure Gemini API
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")

    genai.configure(api_key=api_key)

    # Filter out the post author from potential commenters
    available_personas = [p for p in personas if p.id != post.author_id]

    if not available_personas or limit <= 0:
        return []

    num_commenters = min(limit, len(available_personas))
    selected_commenters = random.sample(available_personas, num_commenters)

    comments = []

    # Generate a comment for each selected persona
    for responder in selected_commenters:
        # Find the post author's name (if available in personas list)
        post_author_name = "another user"
        for p in personas:
            if p.id == post.author_id:
                post_author_name = p.name
                break

        # Build the prompt for this responder
        prompt = f"""You are {responder.name}.
Your backstory: {responder.bio}
Your personality traits: {responder.traits}

You are browsing Reddit and see this post by {post_author_name}:

Title: {post.title}
Body: {post.body}

Write a short, natural comment in response. You can:
- Agree or disagree with the post
- Share a personal anecdote or experience
- Ask a follow-up question
- Add helpful information or debate a point

Keep your comment authentic to your personality and conversational in tone (this is Reddit).
Make it 1-3 sentences unless you have something particularly insightful to share.

You must respond with valid JSON matching this schema:
{{
    "text": "your comment text here",
    "author_id": "{responder.id}",
    "parent_id": "{post.keyword_id}"
}}"""

        # Create the model with JSON response format
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={"response_mime_type": "application/json"},
        )

        # Generate the response with retry logic
        response = generate_with_retry(model, prompt)

        # Parse the JSON response with error handling
        try:
            comment_data = json.loads(response.text)
        except json.JSONDecodeError as e:
            # Try to extract JSON from markdown code blocks if present
            text = response.text.strip()
            if text.startswith("```json") and text.endswith("```"):
                text = text[7:-3].strip()
                comment_data = json.loads(text)
            elif text.startswith("```") and text.endswith("```"):
                text = text[3:-3].strip()
                comment_data = json.loads(text)
            else:
                print(f"JSON Parse Error in comment: {e}")
                print(f"Response text: {response.text[:500]}")
                raise
        
        # Ensure parent_id links back to this post for grouping in exports
        comment_data.setdefault("parent_id", post.keyword_id)

        # Create RedditComment object and add to list
        comment = RedditComment(**comment_data)
        comments.append(comment)

    return comments


def evaluate_post_quality(post: RedditPost) -> Dict[str, any]:
    """Evaluate the quality and authenticity of a Reddit post.
    
    Args:
        post: The RedditPost object to evaluate
    
    Returns:
        Dictionary with score (1-10) and feedback string
    """
    # Configure Gemini API
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")

    genai.configure(api_key=api_key)
    
    # 1. Force JSON mode so Gemini doesn't talk back
    model = genai.GenerativeModel(
        "gemini-2.5-flash", 
        generation_config={"response_mime_type": "application/json"}
    )

    prompt = f"""
    You are a Senior Reddit Content Editor.
    Analyze this post draft:
    Title: {post.title}
    Body: {post.body}
    
    Task:
    Rate it on a scale of 1-10 for "Authenticity". 
    Does it sound like a real human user (good) or a marketing bot (bad)?
    
    Output strictly this JSON:
    {{
        "score": int,
        "feedback": "string explaining the rating"
    }}
    """
    
    # Generate with retry logic
    response = generate_with_retry(model, prompt)
    
    try:
        # Try direct JSON parsing
        return json.loads(response.text)
    except json.JSONDecodeError as e:
        # Try to extract JSON from markdown code blocks if present
        text = response.text.strip()
        try:
            if text.startswith("```json") and text.endswith("```"):
                text = text[7:-3].strip()
                return json.loads(text)
            elif text.startswith("```") and text.endswith("```"):
                text = text[3:-3].strip()
                return json.loads(text)
            else:
                raise e
        except Exception as parse_error:
            print(f"Critique Error: {parse_error}")
            print(f"Response text: {response.text[:500]}")
            return {"score": 5, "feedback": "Error parsing critique"}