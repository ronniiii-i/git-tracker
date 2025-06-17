# git-tracker/generate_svg.py
import requests
import os
import datetime

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
# The `contributionsCollection` gives data for roughly the last 365 days.
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
total_contributions = 0
daily_contributions = {}
try:
    res = requests.post(GRAPHQL_API_URL, headers=headers, json={'query': graphql_query})
    res.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
    data = res.json()
    
    if 'errors' in data:
        print(f"GraphQL errors: {data['errors']}")
        # Fallback to 0 if there are errors, don't exit entirely
        # (This allows the SVG to still be generated, but with 0 values)
        total_contributions = 0
        daily_contributions = {}
    else:
        # Extract data
        user_data = data['data']['user']
        contribution_calendar = user_data['contributionsCollection']['contributionCalendar']
        total_contributions = contribution_calendar['totalContributions']
        
        for week in contribution_calendar['weeks']:
            for day in week['contributionDays']:
                date_obj = datetime.datetime.strptime(day['date'], '%Y-%m-%d').date()
                daily_contributions[date_obj] = day['contributionCount']

except requests.exceptions.RequestException as e:
    print(f"Error fetching GitHub GraphQL data: {e}")
    exit(1) # Exit if we can't even get data

# --- Streak Calculation Functions ---

def calculate_streak_ending_on_date(contributions_data, end_date):
    """Calculates streak ending *on* the specified end_date (inclusive)."""
    streak = 0
    current_date = end_date
    while contributions_data.get(current_date, 0) > 0:
        streak += 1
        current_date -= datetime.timedelta(days=1)
    return streak

def find_longest_streak(daily_contributions):
    longest_streak = 0
    longest_start = None
    longest_end = None

    # Get all unique dates with contributions, sorted
    dates_with_contributions = sorted([d for d, c in daily_contributions.items() if c > 0])
    
    if not dates_with_contributions:
        return 0, None, None

    current_streak = 0
    current_streak_start = None

    for i, date in enumerate(dates_with_contributions):
        if i == 0:
            current_streak = 1
            current_streak_start = date
        else:
            prev_date = dates_with_contributions[i-1]
            # Check if current date is exactly one day after previous
            if date == prev_date + datetime.timedelta(days=1):
                current_streak += 1
            else:
                # Streak broken, update longest if applicable
                if current_streak > longest_streak:
                    longest_streak = current_streak
                    longest_start = current_streak_start
                    longest_end = prev_date # End date of the just-completed streak
                current_streak = 1 # Start new streak
                current_streak_start = date

    # After loop, check if the last streak was the longest
    if current_streak > longest_streak:
        longest_streak = current_streak
        longest_start = current_streak_start
        longest_end = dates_with_contributions[-1] # Last date in the list

    return longest_streak, longest_start, longest_end


# --- Calculate Streaks ---
today = datetime.date.today()
yesterday = today - datetime.timedelta(days=1)

current_streak_calc = 0
current_streak_start_date = None
current_streak_end_date = None

if daily_contributions.get(today, 0) > 0:
    current_streak_calc = calculate_streak_ending_on_date(daily_contributions, today)
    current_streak_end_date = today
    current_streak_start_date = today - datetime.timedelta(days=current_streak_calc - 1)
elif daily_contributions.get(yesterday, 0) > 0:
    # If today has no contribution but yesterday did, the "current" streak ended yesterday.
    current_streak_calc = calculate_streak_ending_on_date(daily_contributions, yesterday)
    current_streak_end_date = yesterday
    current_streak_start_date = yesterday - datetime.timedelta(days=current_streak_calc - 1)


longest_streak_calc, longest_streak_start, longest_streak_end = find_longest_streak(daily_contributions)


# --- Format Dates for Display ---
current_streak_range_str = "N/A"
if current_streak_calc > 0 and current_streak_start_date and current_streak_end_date:
    if current_streak_start_date == current_streak_end_date:
        current_streak_range_str = f"{current_streak_start_date.strftime('%b %d, %Y')}"
    else:
        current_streak_range_str = f"{current_streak_start_date.strftime('%b %d, %Y')} - {current_streak_end_date.strftime('%b %d, %Y')}"
elif total_contributions == 0:
    current_streak_range_str = "No contributions yet"
else: # Current streak is 0 but there were contributions (broken streak)
    current_streak_range_str = "No active streak"

longest_streak_range_str = "N/A"
if longest_streak_calc > 0 and longest_streak_start and longest_streak_end:
    if longest_streak_start == longest_streak_end:
        longest_streak_range_str = f"{longest_streak_start.strftime('%b %d, %Y')}"
    else:
        longest_streak_range_str = f"{longest_streak_start.strftime('%b %d, %Y')} - {longest_streak_end.strftime('%b %d, %Y')}"
elif total_contributions == 0:
    longest_streak_range_str = "No contributions yet"


# --- SVG Generation Logic (now generating two themes) ---

# Define theme colors
themes = {
    "light": {
        "bg_color": "#FFFFFF",
        "text_color": "#24292e",
        "title_color": "#0366d6" # GitHub blue
    },
    "dark": {
        "bg_color": "#0D1117",
        "text_color": "#C9D1D9",
        "title_color": "#58a6ff" # GitHub light blue
    }
}

# Common SVG parameters
line_height = 24 # Increased for more spacing
padding_x = 20
padding_y = 20
font_size_main = 16
font_size_sub = 12

# Content lines (prepared once)
lines_content = [
    f"Total Contributions (last year): {total_contributions}",
    f"Current Streak: {current_streak_calc} days",
    f"  {current_streak_range_str}",
    f"Longest Streak: {longest_streak_calc} days",
    f"  {longest_streak_range_str}"
]

# Calculate dynamic SVG height and width
num_lines = len(lines_content)
svg_height = (num_lines * line_height) + (2 * padding_y)

# Estimate max text width
max_text_width = 0
for line in lines_content:
    # This is a very rough estimate; for precise width, SVG text measurement is needed
    max_text_width = max(max_text_width, len(line) * 8) # Approx 8px per character

svg_width = max(350, max_text_width + (2 * padding_x)) # Ensure minimum width and add padding

# Function to generate SVG for a specific theme
def generate_themed_svg(theme_name, theme_colors, lines):
    svg = f"<svg xmlns='http://www.w3.org/2000/svg' width='{svg_width}' height='{svg_height}'>"
    svg += f"<rect x='0' y='0' width='{svg_width}' height='{svg_height}' fill='{theme_colors['bg_color']}' rx='10'/>" # Rounded corners

    svg += "<style>"
    svg += f"text {{ font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif,Apple Color Emoji,Segoe UI Emoji; fill: {theme_colors['text_color']}; }}"
    svg += "</style>"

    y_pos = padding_y + font_size_main # Starting Y position for first text element
    
    # Title/Header (optional, can be added here if desired)
    # svg += f"<text x='{padding_x}' y='{y_pos}' font-size='{font_size_main + 2}' font-weight='bold' fill='{theme_colors['title_color']}'>GitHub Activity Summary</text>"
    # y_pos += line_height * 1.5 # Extra space after title

    for i, line in enumerate(lines):
        current_y = y_pos + (i * line_height)
        font_size = font_size_main
        fill_color = theme_colors['text_color']
        
        # Apply special styling for date ranges (lines that start with '  ')
        if line.strip().startswith('  '): # Using strip for robustness
            font_size = font_size_sub
            current_y -= (line_height - font_size_sub) / 2 # Adjust y for smaller font
            fill_color = theme_colors['text_color'] # Can make this a lighter shade if desired
        
        # Apply special styling for main stats (first line of each section)
        elif i == 0 or line.startswith("Current Streak") or line.startswith("Longest Streak"):
            font_size = font_size_main
            # fill_color = theme_colors['title_color'] # Optionally highlight main stats


        svg += f"<text x='{padding_x}' y='{current_y}' font-size='{font_size}' fill='{fill_color}'>{line.strip()}</text>"


    svg += "</svg>"
    return svg

# Generate and save SVGs for each theme
for theme_name, theme_colors in themes.items():
    svg_content = generate_themed_svg(theme_name, theme_colors, lines_content)
    file_name = f"tracker-{theme_name}.svg"
    with open(file_name, "w") as f:
        f.write(svg_content)
    print(f"{file_name} generated successfully.")