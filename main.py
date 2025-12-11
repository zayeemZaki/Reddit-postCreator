import concurrent.futures
import io
import os
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st
import xlsxwriter
from dotenv import load_dotenv

from src.agents import generate_comments, generate_post
from src.loader import load_data
from src.scheduler import schedule_posts
from src.schemas import RedditComment, RedditPost

# Load environment variables (API Key)
load_dotenv()

# --- CONFIGURATION ---
DEFAULT_DATA_PATH = "data/SlideForge.xlsx - Company Info.csv"


def _clean_timestamp(value: Any) -> str:
    """Format timestamps as '%Y-%m-%d %H:%M:%S' without microseconds.
    
    Args:
        value: Timestamp value (datetime, string, or None)
    
    Returns:
        Formatted timestamp string or empty string if invalid
    """
    if value is None or value == "":
        return ""
    try:
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return pd.to_datetime(value).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def _drop_unnamed(df: pd.DataFrame) -> pd.DataFrame:
    """Remove any auto-added 'Unnamed' columns from a DataFrame.
    
    Args:
        df: DataFrame to clean
    
    Returns:
        DataFrame with 'Unnamed' columns removed
    """
    return df.loc[:, ~df.columns.str.startswith("Unnamed")]


def generate_single_post_chain(
    persona: Dict[str, Any],
    keyword_entry: Dict[str, Any],
    subreddit: str,
    week_offset: int,
    num_comments: int,
    personas_all: List[Dict[str, Any]]
) -> Tuple[RedditPost, List[RedditComment]]:
    """Generate one post, schedule it, and create timestamped comments.
    
    Args:
        persona: Persona dictionary with id, name, bio, traits
        keyword_entry: Keyword dictionary with keyword, keyword_id, and optional text fields
        subreddit: Target subreddit name
        week_offset: Week offset from current date for scheduling
        num_comments: Maximum number of comments to generate
        personas_all: List of all available persona dictionaries
    
    Returns:
        Tuple of (RedditPost with timestamp, List of RedditComments with timestamps)
    """
    keyword_text = (
        keyword_entry.get("keyword")
        or keyword_entry.get("text")
        or keyword_entry.get("keyword_text")
    )
    keyword_id = keyword_entry.get("keyword_id") or keyword_entry.get("id") or keyword_text

    if not keyword_text:
        raise ValueError("Keyword text missing in keyword entry; check the Keywords block.")

    post = generate_post(persona, keyword_text, subreddit, keyword_id)
    post.keyword_id = keyword_id

    start_date = datetime.now() + timedelta(weeks=week_offset)
    scheduled_post = schedule_posts([post], start_date=start_date)[0]
    post.timestamp = scheduled_post.timestamp

    comments = generate_comments(post, personas_all, limit=num_comments)

    base_ts = pd.to_datetime(_clean_timestamp(post.timestamp))
    for c in comments:
        offset_minutes = random.randint(15, 120)
        comment_dt = base_ts + timedelta(minutes=offset_minutes)
        c.timestamp = comment_dt.strftime("%Y-%m-%d %H:%M:%S")

    return post, comments


def main() -> None:
    """Compact enterprise UI: sidebar-driven campaign generation, tabbed previews, single Excel export.
    
    Streamlit application entrypoint for Social Campaign Scheduler.
    Orchestrates parallel post generation, scheduling, and Excel export.
    """
    st.set_page_config(page_title="Social Campaign Scheduler", layout="wide")

    # Inject CSS to widen sidebar to 400px
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            width: 400px !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Sidebar: Import Data
    with st.sidebar.expander("Import Data", expanded=True):
        uploaded_file = st.file_uploader("Upload Company Info (CSV)", type=["csv"])

    data_source = uploaded_file if uploaded_file else DEFAULT_DATA_PATH
    if not uploaded_file and not os.path.exists(DEFAULT_DATA_PATH):
        st.error(f"File not found: {DEFAULT_DATA_PATH}. Please upload a CSV.")
        return

    # Load data
    try:
        data = load_data(data_source)
        st.sidebar.success(f"Loaded: {data['company'].get('Name', 'Unknown Company')}")
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return

    # Sidebar: Settings
    with st.sidebar.expander("Settings", expanded=True):
        default_posts = data['company'].get('posts_per_week', 3)
        posts_per_week = st.number_input("Posts to Generate", min_value=1, max_value=10, value=default_posts)
        duration_weeks = st.slider("Duration (Weeks)", min_value=1, max_value=4, value=1)
        num_comments = st.slider("Max Comments", min_value=0, max_value=10, value=2)

    # Sidebar: Action
    run_campaign = st.sidebar.button("Run Campaign")

    # Main Area: Title and Download Button Layout
    col1, col2 = st.columns([0.7, 0.3])
    with col1:
        st.title("Social Campaign Scheduler")
    with col2:
        download_placeholder = st.empty()

    if not run_campaign:
        st.write("Ready to process")
        return

    # Processing status
    status = st.status("Processing...", expanded=False)

    all_posts_data = []
    all_comments_data = []
    keywords_source = data.get('keywords', [])

    try:
        for week_idx in range(duration_weeks):
            status.write(f"Generating schedule for week {week_idx + 1}/{duration_weeks}...")
            used_keywords = set()
            futures = []

            with concurrent.futures.ThreadPoolExecutor() as executor:
                for i in range(posts_per_week):
                    available_keywords = [
                        k for k in keywords_source if (k.get('keyword_id') or k.get('id')) not in used_keywords
                    ]

                    if not available_keywords:
                        st.warning("Ran out of unique keywords. Resetting list.")
                        used_keywords.clear()
                        available_keywords = list(keywords_source)

                    keyword_entry = random.choice(available_keywords)
                    keyword_text = (
                        keyword_entry.get('keyword')
                        or keyword_entry.get('text')
                        or keyword_entry.get('keyword_text')
                    )
                    keyword_id = keyword_entry.get('keyword_id') or keyword_entry.get('id') or keyword_text

                    used_keywords.add(keyword_id)

                    persona = random.choice(data['personas'])
                    subreddit = random.choice(data['subreddits'])

                    futures.append(
                        executor.submit(
                            generate_single_post_chain,
                            persona,
                            keyword_entry,
                            subreddit,
                            week_idx,
                            num_comments,
                            data['personas'],
                        )
                    )

                for future in concurrent.futures.as_completed(futures):
                    post, comments = future.result()
                    all_posts_data.append({"post": post, "week_number": week_idx + 1})
                    for c in comments:
                        all_comments_data.append({
                            "comment": c,
                            "week_number": week_idx + 1,
                            "post_keyword": post.keyword_id,
                        })

        # Build DataFrames
        status.update(label="Finalizing export...")

        posts_sorted = sorted(
            all_posts_data,
            key=lambda x: pd.to_datetime(_clean_timestamp(x["post"].timestamp)),
        )

        post_rows = []
        comment_rows = []

        for idx, entry in enumerate(posts_sorted):
            post = entry["post"]
            week_number = entry["week_number"]
            p_id = f"P{idx+1}"

            post_rows.append({
                "Week_Number": week_number,
                "post_id": p_id,
                "subreddit": post.subreddit,
                "title": post.title,
                "body": post.body,
                "author_username": post.author_id,
                "timestamp": _clean_timestamp(post.timestamp),
                "keyword_ids": post.keyword_id,
            })

            related_comments = [c for c in all_comments_data if c["post_keyword"] == post.keyword_id]

            for c_idx, c_entry in enumerate(related_comments):
                comment = c_entry["comment"]
                c_id = f"C{idx+1}-{c_idx+1}"
                comment_rows.append({
                    "Week_Number": c_entry["week_number"],
                    "comment_id": c_id,
                    "post_id": p_id,
                    "parent_comment_id": getattr(comment, "parent_comment_id", ""),
                    "comment_text": comment.text,
                    "username": comment.author_id,
                    "timestamp": _clean_timestamp(getattr(comment, "timestamp", "")),
                })

        df_master_posts = pd.DataFrame(post_rows)
        df_master_comments = pd.DataFrame(comment_rows)

        df_master_posts = df_master_posts.loc[:, ~df_master_posts.columns.str.startswith("Unnamed")]
        df_master_comments = df_master_comments.loc[:, ~df_master_comments.columns.str.startswith("Unnamed")]

        post_cols = [
            "Week_Number",
            "post_id",
            "subreddit",
            "title",
            "body",
            "author_username",
            "timestamp",
            "keyword_ids",
        ]
        df_master_posts = df_master_posts.reindex(columns=post_cols)

        if not df_master_comments.empty and "timestamp" in df_master_comments.columns:
            df_master_comments["timestamp"] = pd.to_datetime(df_master_comments["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")

        comment_cols = [
            "Week_Number",
            "comment_id",
            "post_id",
            "parent_comment_id",
            "comment_text",
            "username",
            "timestamp",
        ]
        df_master_comments = df_master_comments.reindex(columns=comment_cols)

        df_posts = df_master_posts
        df_comments = df_master_comments

        # Excel export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_posts.to_excel(writer, index=False, sheet_name='Content Calendar', startrow=0)
            start_row = len(df_posts) + 4
            df_comments.to_excel(writer, index=False, sheet_name='Content Calendar', startrow=start_row)

            workbook = writer.book
            worksheet = writer.sheets['Content Calendar']
            header_fmt = workbook.add_format({'bold': True, 'fg_color': '#4F81BD', 'font_color': 'white', 'border': 1})

            for col_num, value in enumerate(df_posts.columns.values):
                worksheet.write(0, col_num, value, header_fmt)
                worksheet.set_column(col_num, col_num, 25)

            for col_num, value in enumerate(df_comments.columns.values):
                worksheet.write(start_row, col_num, value, header_fmt)

        output.seek(0)

        # Tabbed previews
        tabs = st.tabs(["Posts", "Comments"])
        with tabs[0]:
            st.dataframe(df_posts, use_container_width=True)
        with tabs[1]:
            st.dataframe(df_comments, use_container_width=True)

        # Main area download button (top right, primary style)
        download_placeholder.download_button(
            label="Download Result",
            data=output,
            file_name="Content_Calendar.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )

        status.update(label="Processing complete", state="complete", expanded=False)

    except Exception as e:
        st.error(f"An error occurred during generation: {e}")
        raise e


if __name__ == "__main__":
    main()
