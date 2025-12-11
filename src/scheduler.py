import random
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple

from .schemas import RedditPost


class WeekScheduler:
    """Schedules Reddit posts across a week while enforcing collision rules.
    
    Rules:
        - No more than 1 post per subreddit per day
        - No repeated keywords in the same week
    """
    
    def __init__(self, start_date: datetime = None) -> None:
        """Initialize the scheduler.
        
        Args:
            start_date: Starting date for the week (defaults to next Monday)
        """
        if start_date is None:
            # Default to next Monday
            today = datetime.now()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            start_date = today + timedelta(days=days_until_monday)
            start_date = start_date.replace(hour=9, minute=0, second=0, microsecond=0)
        
        self.start_date = start_date
        self.schedule: Dict[int, List[Dict]] = {day: [] for day in range(7)}  # 0=Monday, 6=Sunday
    
    def _get_posting_times(self, day: int) -> List[datetime]:
        """Generate optimal posting times for a given day.
        
        Args:
            day: Day of week (0=Monday, 6=Sunday)
        
        Returns:
            List of datetime objects with good posting times
        """
        base_date = self.start_date + timedelta(days=day)
        
        # Reddit peak times (in hours): 6-8am, 12-1pm, 7-9pm
        peak_times = [
            base_date.replace(hour=7, minute=random.randint(0, 59)),
            base_date.replace(hour=12, minute=random.randint(0, 59)),
            base_date.replace(hour=19, minute=random.randint(0, 59)),
        ]
        
        return peak_times
    
    def schedule_posts(self, posts: List[RedditPost]) -> List[RedditPost]:
        """Schedule posts across the week while respecting collision rules.
        
        Args:
            posts: List of RedditPost objects to schedule
        
        Returns:
            List of RedditPost objects with timestamp field populated, sorted chronologically
        """
        scheduled_posts = []
        used_keywords: Set[str] = set()
        
        # Track which subreddits have been used on each day
        daily_subreddits: Dict[int, Set[str]] = {day: set() for day in range(7)}
        
        # Shuffle posts for randomness
        posts_to_schedule = posts.copy()
        random.shuffle(posts_to_schedule)
        
        post_counter = 1
        
        for post in posts_to_schedule:
            # Check keyword collision
            if post.keyword_id in used_keywords:
                continue  # Skip this post - keyword already used this week
            
            # Try to find a day where this subreddit hasn't been used
            scheduled = False
            attempts = list(range(7))
            random.shuffle(attempts)
            
            for day in attempts:
                if post.subreddit not in daily_subreddits[day]:
                    # Found a valid day!
                    posting_times = self._get_posting_times(day)
                    
                    # Choose a random posting time from the available times
                    timestamp = random.choice(posting_times)
                    
                    # Set the timestamp on the post object
                    post.timestamp = timestamp.isoformat()
                    
                    # Update tracking
                    daily_subreddits[day].add(post.subreddit)
                    used_keywords.add(post.keyword_id)
                    scheduled_posts.append(post)
                    
                    post_counter += 1
                    scheduled = True
                    break
            
            if not scheduled and post.keyword_id not in used_keywords:
                # Could not schedule due to subreddit conflicts
                # Try to schedule anyway on the day with least conflict
                min_conflicts_day = min(range(7), key=lambda d: len(daily_subreddits[d]))
                
                posting_times = self._get_posting_times(min_conflicts_day)
                timestamp = random.choice(posting_times)
                
                # Set the timestamp on the post object
                post.timestamp = timestamp.isoformat()
                
                daily_subreddits[min_conflicts_day].add(post.subreddit)
                used_keywords.add(post.keyword_id)
                scheduled_posts.append(post)
                
                post_counter += 1
        
        # Sort by timestamp (convert ISO string back to datetime for sorting)
        from datetime import datetime as dt
        scheduled_posts.sort(key=lambda x: dt.fromisoformat(x.timestamp))
        
        return scheduled_posts
    
    def get_schedule_summary(self) -> str:
        """Get a human-readable summary of the scheduled posts.
        
        Returns:
            Formatted string with schedule overview
        """
        summary = []
        summary.append(f"\n{'='*80}")
        summary.append(f"WEEK SCHEDULE: {self.start_date.strftime('%B %d, %Y')}")
        summary.append(f"{'='*80}\n")
        
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        for day_idx in range(7):
            day_posts = sorted(self.schedule[day_idx], key=lambda x: x["timestamp"])
            
            if day_posts:
                date = self.start_date + timedelta(days=day_idx)
                summary.append(f"\n{day_names[day_idx]}, {date.strftime('%B %d')}")
                summary.append("-" * 80)
                
                for post in day_posts:
                    warning = f" ⚠️  {post['warning']}" if 'warning' in post else ""
                    summary.append(f"  {post['post_id']} | {post['time']} | r/{post['subreddit']}")
                    summary.append(f"      Keyword: {post['keyword_id']} | Author: {post['author_id']}")
                    summary.append(f"      Title: {post['title'][:70]}{'...' if len(post['title']) > 70 else ''}{warning}")
                    summary.append("")
        
        total_posts = sum(len(self.schedule[day]) for day in range(7))
        summary.append(f"{'='*80}")
        summary.append(f"Total Posts Scheduled: {total_posts}")
        summary.append(f"{'='*80}\n")
        
        return "\n".join(summary)
    
    def validate_schedule(self) -> Tuple[bool, List[str]]:
        """Validate the schedule against collision rules.
        
        Returns:
            Tuple of (is_valid, list_of_violations)
        """
        violations = []
        all_keywords = set()
        
        for day_idx in range(7):
            day_posts = self.schedule[day_idx]
            day_subreddits = [p['subreddit'] for p in day_posts]
            
            # Check for duplicate subreddits on same day
            if len(day_subreddits) != len(set(day_subreddits)):
                duplicates = [sr for sr in set(day_subreddits) if day_subreddits.count(sr) > 1]
                violations.append(f"Day {day_idx}: Multiple posts to {duplicates}")
            
            # Collect keywords
            for post in day_posts:
                keyword = post['keyword_id']
                if keyword in all_keywords:
                    violations.append(f"Keyword '{keyword}' used multiple times in the week")
                all_keywords.add(keyword)
        
        return len(violations) == 0, violations


def schedule_week_posts(posts: List[RedditPost], start_date: datetime = None) -> List[RedditPost]:
    """Convenience function to schedule posts for a week.
    
    Args:
        posts: List of RedditPost objects to schedule
        start_date: Optional start date for the week
    
    Returns:
        List of scheduled posts with timestamps and IDs
    """
    scheduler = WeekScheduler(start_date)
    scheduled_posts = scheduler.schedule_posts(posts)
    
    # Print summary
    print(scheduler.get_schedule_summary())
    
    # Validate
    is_valid, violations = scheduler.validate_schedule()
    if not is_valid:
        print("SCHEDULE VIOLATIONS DETECTED:")
        for violation in violations:
            print(f"  - {violation}")
        print()
    else:
        print("Schedule validated: No collisions detected!\n")
    
    return scheduled_posts


# Backward-compatible alias
schedule_posts = schedule_week_posts
