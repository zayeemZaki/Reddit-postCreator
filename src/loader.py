import pandas as pd
import io
import csv
from typing import Dict, Any, List, Union
from .schemas import Persona

def load_data(filepath: Union[str, Any]) -> Dict[str, Any]:
    """
    Parses the multi-section CSV file containing Company Info, Personas, and Keywords.
    
    Args:
        filepath: Either a string path to a CSV file, or a Streamlit UploadedFile object
    
    Returns:
        Dictionary containing company info, personas, subreddits, and keywords
    """
    # Handle both file path strings and Streamlit UploadedFile objects
    if isinstance(filepath, str):
        # Traditional file path
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        # Streamlit UploadedFile object
        content = filepath.getvalue().decode('utf-8')

    # 1. Split the file into sections based on known headers
    try:
        # Find where the Personas table starts
        persona_header = "Username,Info"
        persona_start = content.index(persona_header)
        
        # Find where the Keywords table starts
        keyword_header = "keyword_id,keyword"
        keyword_start = content.index(keyword_header)

        # Ensure ordering: Personas block must appear before Keywords block
        if persona_start > keyword_start:
            raise ValueError("Invalid CSV layout: Personas block must appear before Keywords block.")
    except ValueError as e:
        raise ValueError(f"Could not find expected headers in CSV. Error: {e}")

    # Slice the content into three raw string blocks
    top_section_raw = content[:persona_start]
    persona_section_raw = content[persona_start:keyword_start]
    keyword_section_raw = content[keyword_start:]

    # --- Section 1: Parse Company Info & Subreddits ---
    company_info = {}
    subreddits = []
    
    reader = csv.reader(io.StringIO(top_section_raw))
    is_subreddit_section = False
    
    for row in reader:
        if not row: continue 
        
        key = row[0].strip()
        
        if key == "Subreddits":
            is_subreddit_section = True
            if len(row) > 1 and row[1]:
                # Handle multi-line subreddit values (split by newline)
                subreddit_value = row[1].strip()
                if '\n' in subreddit_value:
                    # Split by newline and clean each subreddit
                    for sub in subreddit_value.split('\n'):
                        sub = sub.strip()
                        if sub:  # Only add non-empty strings
                            subreddits.append(sub)
                else:
                    subreddits.append(subreddit_value)
            continue
            
        if key == "Number of posts per week":
            is_subreddit_section = False
            if len(row) > 1:
                company_info['posts_per_week'] = int(row[1])
            continue
            
        if is_subreddit_section:
            if key.startswith("r/"):
                subreddits.append(key)
        else:
            if len(row) > 1:
                company_info[key] = row[1]

    # --- Section 2: Parse Personas (FIXED) ---
    persona_df = pd.read_csv(io.StringIO(persona_section_raw))
    persona_df = persona_df.loc[:, ~persona_df.columns.str.startswith("Unnamed")]
    
    # FIX: Drop rows where Username is missing/empty (this removes the trailing commas)
    persona_df = persona_df.dropna(subset=['Username'])
    
    personas = []
    for _, row in persona_df.iterrows():
        # Double check to ensure we have a string
        if not isinstance(row['Username'], str):
            continue
            
        p = Persona(
            id=row['Username'],
            name=row['Username'].replace('_', ' ').title(), 
            bio=row['Info'],
            traits="To be inferred from bio" 
        )
        personas.append(p)

    # --- Section 3: Parse Keywords ---
    keyword_df = pd.read_csv(io.StringIO(keyword_section_raw))
    keyword_df = keyword_df.loc[:, ~keyword_df.columns.str.startswith("Unnamed")]
    # Safety: drop empty keywords too if any
    keyword_df = keyword_df.dropna(subset=['keyword'])
    keywords = keyword_df.to_dict('records')

    return {
        "company": company_info,
        "subreddits": subreddits,
        "personas": personas,
        "keywords": keywords
    }