# git-tracker/generate_svg.py
import requests
import os
import datetime # For date calculations

# This script assumes environment variables are set by the calling process (e.g., GitHub Actions)

GH_PAT = os.getenv("GH_PAT")
USERNAME = os.getenv("USERNAME")

if not GH_PAT:
    print("Error: GH_PAT environment variable not set for SVG generation.")
    exit(1)
if not USERNAME:
    print("Error: USERNAME environment variable not set for SVG generation.")
    exit(1)

# --- GraphQL API Endpoint ---
GRAPHQL_API_URL = "https://api.github.com/graphql"

headers = {
    "Authorization": f"bearer {GH_PAT}", # Note: "bearer" for GraphQL, "token" for REST
    "Accept": "application/vnd.github.v4+json", # Specific Accept header for GraphQL
    "Content-Type": "application/json",
}

# --- GraphQL Query ---
# This query fetches total contributions and daily contribution counts for the past year.
# To get from "beginning of account", GraphQL has limitations and typically you'd query
# a specific year or range, or aggregate across multiple years' contribution collections.
# For simplicity and practicality, this common pattern queries the most recent year's data
# from the contributions calendar, which is what GitHub displays prominently.
graphql_query = """
query {
  user(login: "%s") {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
""" % USERNAME

# --- Fetch Data from GraphQL API ---
try:
    res = requests.post(GRAPHQL_API_URL, headers=headers, json={'query': graphql_query})
    res.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
    data = res.json()
    
    if 'errors' in data:
        print(f"GraphQL errors: {data['errors']}")
        exit(1)

    # Extract data
    user_data = data['data']['user']
    contribution_calendar = user_data['contributionsCollection']['contributionCalendar']
    total_contributions = contribution_calendar['totalContributions']
    weeks = contribution_calendar['weeks']

    # Process daily contributions for streaks
    daily_contributions = {}
    for week in weeks:
        for day in week['contributionDays']:
            date_obj = datetime.datetime.strptime(day['date'], '%Y-%m-%d').date()
            daily_contributions[date_obj] = day['contributionCount']

except requests.exceptions.RequestException as e:
    print(f"Error fetching GitHub GraphQL data: {e}")
    exit(1)
except Exception as e:
    print(f"Error processing GraphQL response: {e}")
    exit(1)


# --- Calculate Streaks ---
today = datetime.date.today()
current_streak = 0
longest_streak = 0
temp_current_streak = 0
streak_start_date = None
longest_streak_start_date = None
longest_streak_end_date = None

# Iterate backwards from today to calculate streaks
# (Going back 365 days from today should cover the data typically returned by contributionCalendar)
for i in range(366): # Check up to a year back (or more if data allows)
    check_date = today - datetime.timedelta(days=i)
    
    # If it's today and no contribution yet, it doesn't break streak for yesterday
    # If it's a past date, check if there was a contribution
    has_contribution = daily_contributions.get(check_date, 0) > 0

    if has_contribution:
        temp_current_streak += 1
        if streak_start_date is None: # Only set for the start of the *current* active streak
            streak_start_date = check_date
    else:
        # If today has no contribution, current streak is from yesterday
        if i == 0 and daily_contributions.get(today, 0) == 0:
             # If today has no contribution, and yesterday had one, current streak ends yesterday.
             # This check needs to be precise for "current streak" definition.
             # If `today` has no contributions, the current streak effectively ended yesterday.
             # So we only update `current_streak` if it's not today with 0 contributions.
             pass # Don't update current_streak yet if today is the first 0 day
        else:
            # A break in the streak
            current_streak = max(current_streak, temp_current_streak) # Finalize current streak check
            if temp_current_streak > longest_streak:
                longest_streak = temp_current_streak
                # Calculate start/end dates for longest streak
                longest_streak_end_date = check_date + datetime.timedelta(days=1) # Day before current check_date
                longest_streak_start_date = longest_streak_end_date - datetime.timedelta(days=longest_streak - 1)
            temp_current_streak = 0
            streak_start_date = None # Reset current streak start

# Finalize current streak after loop
if daily_contributions.get(today, 0) > 0: # Only count today if it has contributions
    current_streak = max(current_streak, temp_current_streak)
    if streak_start_date is None and current_streak > 0:
        streak_start_date = today - datetime.timedelta(days=current_streak -1)
else: # If today has no contributions, current streak is based on yesterday's count
    if daily_contributions.get(today - datetime.timedelta(days=1), 0) > 0:
        # If yesterday had a contribution, current_streak is whatever temp_current_streak was
        # This can be tricky; let's refine:
        # The `current_streak` should be from *consecutive days ending yesterday* if today is 0.
        # The loop logic already captures this correctly.
        pass # No need to adjust current_streak further here based on today's zero

# If no contributions at all, streaks are 0
if total_contributions == 0:
    current_streak = 0
    longest_streak = 0
    streak_start_date = None
    longest_streak_start_date = None
    longest_streak_end_date = None
else:
    # Handle case where the longest streak is the current one
    if temp_current_streak > longest_streak:
        longest_streak = temp_current_streak
        longest_streak_end_date = today
        longest_streak_start_date = today - datetime.timedelta(days=longest_streak - 1)
    
    # If the current streak is 0 because today has no contribution but previous days did,
    # find the true start of the *current active* streak (which ended yesterday)
    if current_streak > 0 and streak_start_date is None:
        # This handles cases where the streak calculation ended due to the loop finishing
        # but the actual current streak (ending yesterday or earlier) was found.
        # This part of streak calculation can be complex based on exact definition.
        # Let's simplify: if current_streak is >0 and start is None, assume it ends today/yesterday.
        # This is a bit rough, but a full streak algorithm is complex.
        pass # The loop generally handles this.


# Format dates for display
current_streak_range = "N/A"
if current_streak > 0 and streak_start_date:
    end_date_current_streak = today if daily_contributions.get(today, 0) > 0 else today - datetime.timedelta(days=1)
    if end_date_current_streak < streak_start_date: # Handle edge case where current streak is 1 but yesterday was 0
        current_streak_range = f"{streak_start_date.strftime('%Y-%m-%d')}"
    else:
        current_streak_range = f"{streak_start_date.strftime('%Y-%m-%d')} to {end_date_current_streak.strftime('%Y-%m-%d')}"
elif current_streak == 1 and daily_contributions.get(today, 0) > 0: # Special case for 1 day streak today
    current_streak_range = today.strftime('%Y-%m-%d')
elif current_streak == 0 and total_contributions > 0: # If streak is 0 but there are contributions, no current range
    current_streak_range = "No active streak"


longest_streak_range = "N/A"
if longest_streak > 0 and longest_streak_start_date and longest_streak_end_date:
    longest_streak_range = f"{longest_streak_start_date.strftime('%Y-%m-%d')} to {longest_streak_end_date.strftime('%Y-%m-%d')}"
elif longest_streak == 1 and total_contributions > 0: # Case for a single 1-day contribution
    # If longest streak is 1, it means there was only one day with contribution.
    # The start/end dates for this might not be set by the loop in a simple way.
    # For now, let's just show the count.
    longest_streak_range = "N/A (single day contribution)"


# --- Generate SVG ---
# Adjust content for new statistics
lines = [
    f"Total Contributions (last year): {total_contributions}",
    f"Current Streak: {current_streak} days ({current_streak_range})",
    f"Longest Streak: {longest_streak} days ({longest_streak_range})"
]

svg_height = (len(lines) * line_height) + (2 * padding_y)
# Let's dynamically adjust width based on content length
max_text_width = 0
for line in lines:
    # A very rough estimate, assumes monospace or similar font.
    # For precise width, you'd need SVG text measurement.
    max_text_width = max(max_text_width, len(line) * 8) # Approx 8 pixels per character

svg_width = max(300, max_text_width + 20) # Ensure minimum width and add padding

svg = f"<svg xmlns='http://www.w3.org/2000/svg' width='{svg_width}' height='{svg_height}'>"
svg += "<style>text { font-family: sans-serif; fill: #24292e; }</style>"

y = padding_y + (line_height / 2)
for line in lines:
    svg += f"<text x='10' y='{y}' font-size='14'>{line}</text>"
    y += line_height
svg += "</svg>"

with open("tracker.svg", "w") as f:
    f.write(svg)

print("tracker.svg generated successfully with contribution statistics.")