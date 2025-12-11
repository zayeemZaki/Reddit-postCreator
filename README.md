# Social Campaign Scheduler

A streamlined Streamlit app for generating persona-driven Reddit posts, scheduled content calendars, and downloadable Excel outputs.

---

## What It Does

- Generate posts and comments from uploaded company/persona/keyword data
- Run multi-week campaigns with parallel generation for faster turnaround
- Auto-schedule posts with collision avoidance and realistic timestamps
- Export a single Excel file (posts on top, comments below) for easy delivery
- Enforce clean formatting (no salutations, no markdown styling) in generated text

---

## Quick Start

### Requirements
- Python 3.10+
- Google Generative AI key (`GOOGLE_API_KEY`)

### Setup
```bash
git clone https://github.com/yourusername/reddit-postcreater.git
cd reddit-postcreater
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:
```
GOOGLE_API_KEY=your_api_key_here
```

### Run the app
```bash
streamlit run main.py
```
1) Upload `data/company_info.csv` (or use your own CSV) in the sidebar
2) Adjust posts/week, duration (weeks), and max comments
3) Click Run Campaign
4) Preview Posts/Comments tabs
5) Download the Excel file (Content_Calendar.xlsx)

---

## Input Data (CSV)

Expected columns (example in `data/company_info.csv`):
- Company info: `Name`, `posts_per_week`
- Personas: `persona_id`, `persona_name`, `persona_bio`, `persona_traits`
- Keywords: `keyword_id`, `keyword`
- Subreddits: `subreddit`

---

## How It Works

1. Load company data, personas, keywords, and subreddits from CSV
2. For each week and post slot, choose a persona, keyword, and subreddit
3. Generate post text and schedule it with realistic timestamps
4. Generate comments from other personas, timestamped after the post
5. Export a single Excel workbook with posts first, comments after a spacer

---

## Notable Details

- Parallel generation uses `ThreadPoolExecutor` for I/O-bound model calls
- Scheduling prevents subreddit/day collisions and repeats keywords per week
- Comments are plain text: no markdown emphasis, no greetings/salutations
- Sidebar width fixed for clarity; primary download button in the main header

---

## Testing

```bash
python -m pytest
```

---

## Project Structure

```
main.py                  # Streamlit entrypoint
src/
    agents.py              # Content generation helpers
    loader.py              # CSV ingestion
    scheduler.py           # Weekly scheduling logic
    schemas.py             # Pydantic models
tests/                   # Basic test suite
data/                    # Sample/input CSVs
```

---

## Troubleshooting

- Missing `google.generativeai`: `pip install google-generativeai`
- Missing `GOOGLE_API_KEY`: set it in `.env`
- Streamlit not found: `pip install streamlit`
- Empty outputs: verify your CSV columns match the expected headers

---

## License

MIT License

---

## Contact

For questions or issues, open a GitHub issue or email your maintainer contact.
