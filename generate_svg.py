import requests
import os
import datetime

GH_PAT = os.getenv("GH_PAT")
USERNAME = os.getenv("USERNAME")

if not GH_PAT:
    print("Error: GH_PAT environment variable not set for SVG generation.")
    exit(1)
if not USERNAME:
    print("Error: USERNAME environment variable not set for SVG generation.")
    exit(1)


GRAPHQL_API_URL = "https://api.github.com/graphql"

headers = {
    "Authorization": f"bearer {GH_PAT}",
    "Accept": "application/vnd.github.v4+json",
    "Content-Type": "application/json",
}

# --- GraphQL Query ---
# This query fetches total contributions and daily contribution counts for the past year (approx 365 days).
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
contribution_data_start_date = None # To track the earliest date of fetched data
contribution_data_end_date = None   # To track the latest date of fetched data

try:
    res = requests.post(GRAPHQL_API_URL, headers=headers, json={'query': graphql_query})
    res.raise_for_status()
    data = res.json()
    
    if 'errors' in data:
        print(f"GraphQL errors: {data['errors']}")
        # Continue with 0 values if there are GraphQL-specific errors, to still generate an SVG
        total_contributions = 0
        daily_contributions = {}
    else:
        user_data = data['data']['user']
        contribution_calendar = user_data['contributionsCollection']['contributionCalendar']
        total_contributions = contribution_calendar['totalContributions']
        
        all_dates_in_data = []
        for week in contribution_calendar['weeks']:
            for day in week['contributionDays']:
                date_obj = datetime.datetime.strptime(day['date'], '%Y-%m-%d').date()
                daily_contributions[date_obj] = day['contributionCount']
                all_dates_in_data.append(date_obj)
        
        if all_dates_in_data:
            contribution_data_start_date = min(all_dates_in_data)
            contribution_data_end_date = max(all_dates_in_data)
        else: # No data for some reason
            contribution_data_start_date = datetime.date.today() - datetime.timedelta(days=364)
            contribution_data_end_date = datetime.date.today()

except requests.exceptions.RequestException as e:
    print(f"Error fetching GitHub GraphQL data: {e}")
    exit(1) # Exit if we can't connect to GitHub API at all

except Exception as e:
    print(f"Error processing GraphQL response or during data extraction: {e}")
    total_contributions = 0 # Fallback values
    daily_contributions = {}
    contribution_data_start_date = datetime.date.today() - datetime.timedelta(days=364)
    contribution_data_end_date = datetime.date.today()


# --- Streak Calculation Functions ---

def calculate_streak_ending_on_date(contributions_data, end_date):
    """Calculates streak ending *on* the specified end_date (inclusive)."""
    streak = 0
    current_date = end_date
    # Loop backward while there are contributions on current_date
    while contributions_data.get(current_date, 0) > 0:
        streak += 1
        current_date -= datetime.timedelta(days=1)
    return streak

def find_longest_streak(daily_contributions):
    longest_streak = 0
    longest_start = None
    longest_end = None

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
            if date == prev_date + datetime.timedelta(days=1):
                current_streak += 1
            else:
                if current_streak > longest_streak:
                    longest_streak = current_streak
                    longest_start = current_streak_start
                    longest_end = prev_date
                current_streak = 1
                current_streak_start = date

    if current_streak > longest_streak:
        longest_streak = current_streak
        longest_start = current_streak_start
        longest_end = dates_with_contributions[-1]

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
    current_streak_calc = calculate_streak_ending_on_date(daily_contributions, yesterday)
    current_streak_end_date = yesterday
    current_streak_start_date = yesterday - datetime.timedelta(days=current_streak_calc - 1)


longest_streak_calc, longest_streak_start, longest_streak_end = find_longest_streak(daily_contributions)


# --- Format Dates for Display ---
date_format_str = '%b %d, %Y'

# Total Contributions Date Range (reflects fetched data's range)
total_contributions_range_str = "N/A"
if contribution_data_start_date and contribution_data_end_date:
    if contribution_data_start_date == contribution_data_end_date:
        total_contributions_range_str = f"{contribution_data_start_date.strftime(date_format_str)}"
    else:
        total_contributions_range_str = f"{contribution_data_start_date.strftime(date_format_str)} - {contribution_data_end_date.strftime(date_format_str)}"
elif total_contributions == 0:
    total_contributions_range_str = "No contributions yet"

current_streak_range_str = "N/A"
if current_streak_calc > 0 and current_streak_start_date and current_streak_end_date:
    if current_streak_start_date == current_streak_end_date:
        current_streak_range_str = f"{current_streak_start_date.strftime(date_format_str)}"
    else:
        current_streak_range_str = f"{current_streak_start_date.strftime(date_format_str)} - {current_streak_end_date.strftime(date_format_str)}"
elif total_contributions == 0:
    current_streak_range_str = "No contributions yet"
else: # Current streak is 0 but there were contributions (broken streak)
    current_streak_range_str = "No active streak"

longest_streak_range_str = "N/A"
if longest_streak_calc > 0 and longest_streak_start and longest_streak_end:
    if longest_streak_start == longest_streak_end:
        longest_streak_range_str = f"{longest_streak_start.strftime(date_format_str)}"
    else:
        longest_streak_range_str = f"{longest_streak_start.strftime(date_format_str)} - {longest_streak_end.strftime(date_format_str)}"
elif total_contributions == 0:
    longest_streak_range_str = "No contributions yet"


# --- SVG Generation Parameters ---

# Fixed dimensions for the overall SVG and columns
svg_width = 600
svg_height = 160
column_width = svg_width / 3
center_x_col1 = column_width / 2
center_x_col2 = column_width + (column_width / 2)
center_x_col3 = (2 * column_width) + (column_width / 2)

# Styling parameters
font_family = "-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif,Apple Color Emoji,Segoe UI Emoji"
font_size_main = 42 # For numbers
font_size_label = 16 # For "Total Contributions", "Current Streak", "Longest Streak"
font_size_date = 13 # For date ranges
line_spacing = 6 # Space between number and label, and label and date

# Flame icon (Octicons flame icon path)
# viewBox="0 0 16 16", so scaling for 40x40 area
flame_icon_path = "M5.426 1.424A.5.5 0 016 1h4a.5.5 0 01.574.424l.64 3.202a.5.5 0 01-.15.485l-1.297 1.296a.5.5 0 01-.328.146h-2.92a.5.5 0 01-.328-.146L4.936 5.111a.5.5 0 01-.15-.485l.64-3.202zM12.923 8.358a.5.5 0 00-.707 0L10.3 10.273l-.478-.478a.5.5 0 00-.707 0L8.03 10.358a.5.5 0 00.707.707l.99-.99.57.57a.5.5 0 00.707 0l.99-.99a.5.5 0 000-.707zM14 6H2a.5.5 0 000 1h12a.5.5 0 000-1zm-2.586 7.414a.5.5 0 00-.707 0L9.03 15.03a.5.5 0 00.707.707l2.122-2.121a.5.5 0 000-.707zM3.864 12.273a.5.5 0 000 .707L6.03 15.03a.5.5 0 00.707-.707L4.571 12.273a.5.5 0 00-.707 0z"

# Define theme colors
themes = {
    "light": {
        "bg_color": "#FFFFFF",
        "text_color": "#24292e",
        "primary_color": "#0366d6", # GitHub blue
        "line_color": "#e1e4e8" # Light grey separator
    },
    "dark": {
        "bg_color": "#0D1117",
        "text_color": "#C9D1D9",
        "primary_color": "#58a6ff", # GitHub light blue
        "line_color": "#30363d" # Dark grey separator
    }
}

# Function to generate SVG for a specific theme
def generate_themed_svg(theme_name, theme_colors):
    svg = f"<svg xmlns='http://www.w3.org/2000/svg' width='{svg_width}' height='{svg_height}'>"
    svg += f"<rect x='0' y='0' width='{svg_width}' height='{svg_height}' fill='{theme_colors['bg_color']}' rx='10'/>" # Background with rounded corners

    # Global styles
    svg += "<style>"
    svg += f"text {{ font-family: {font_family}; fill: {theme_colors['text_color']}; text-anchor: middle; }}"
    svg += f".main-number {{ font-size: {font_size_main}px; font-weight: bold; }}"
    svg += f".label-text {{ font-size: {font_size_label}px; }}"
    svg += f".date-range {{ font-size: {font_size_date}px; fill: {theme_colors['text_color']}; }}" # Can be lighter if desired
    svg += f".primary-color-text {{ fill: {theme_colors['primary_color']}; }}"
    svg += "</style>"

    # --- Column 1: Total Contributions ---
    # Number
    svg += f"<text x='{center_x_col1}' y='{svg_height / 2 - font_size_label}' class='main-number'>{total_contributions}</text>"
    # Label
    svg += f"<text x='{center_x_col1}' y='{svg_height / 2 + font_size_label/2 + line_spacing}' class='label-text'>Total Contributions</text>"
    # Date Range
    svg += f"<text x='{center_x_col1}' y='{svg_height / 2 + font_size_label/2 + line_spacing + font_size_label + line_spacing/2}' class='date-range'>{total_contributions_range_str}</text>"

    # --- Column 2: Current Streak ---
    # Icon and Number - position icon slightly above and to the left of number center
    icon_size = 10
    icon_x = center_x_col2 - (icon_size / 2) # Center icon
    icon_y = svg_height / 2 - font_size_label - icon_size/2 - 5 # Position above number and label
    
    # Flame icon circle (background for icon)
    # The example has a circle around the flame
    circle_radius = 28 # Adjust as needed
    circle_y = svg_height / 2 - font_size_label - icon_size/2 + 10 # Adjust vertically for alignment
    svg += f"<circle cx='{center_x_col2}' cy='{circle_y}' r='{circle_radius}' stroke='{theme_colors['primary_color']}' stroke-width='3' fill='none' />"

    # Flame icon itself
    # Calculate scale and translate to fit 40x40 in 16x16 viewbox and center it
    scale_factor = icon_size / 16 # Scale from 16x16 to desired icon_size
    translate_x = center_x_col2 - (16 * scale_factor) / 2 # Center it relative to icon_size
    translate_y = circle_y - (16 * scale_factor) / 2 # Center it relative to icon_size
    
    # Using transform to scale and position the flame path
    # Flame path from viewBox="0 0 16 16"
    flame_transform = f"translate({translate_x} {translate_y}) scale({scale_factor})"
    svg += f"<path d='{flame_icon_path}' fill='{theme_colors['primary_color']}' transform='{flame_transform}'/>"


    # Number
    svg += f"<text x='{center_x_col2}' y='{svg_height / 2 - font_size_label}' class='main-number'>{current_streak_calc}</text>"
    # Label
    svg += f"<text x='{center_x_col2}' y='{svg_height / 2 + font_size_label/2 + line_spacing}' class='label-text primary-color-text'>Current Streak</text>"
    # Date Range
    svg += f"<text x='{center_x_col2}' y='{svg_height / 2 + font_size_label/2 + line_spacing + font_size_label + line_spacing/2}' class='date-range'>{current_streak_range_str}</text>"


    # --- Column 3: Longest Streak ---
    # Number
    svg += f"<text x='{center_x_col3}' y='{svg_height / 2 - font_size_label}' class='main-number'>{longest_streak_calc}</text>"
    # Label
    svg += f"<text x='{center_x_col3}' y='{svg_height / 2 + font_size_label/2 + line_spacing}' class='label-text'>Longest Streak</text>"
    # Date Range
    svg += f"<text x='{center_x_col3}' y='{svg_height / 2 + font_size_label/2 + line_spacing + font_size_label + line_spacing/2}' class='date-range'>{longest_streak_range_str}</text>"

    # --- Vertical Separator Lines ---
    line_y1 = svg_height * 0.25 # Start 25% down
    line_y2 = svg_height * 0.75 # End 75% down
    
    svg += f"<line x1='{column_width}' y1='{line_y1}' x2='{column_width}' y2='{line_y2}' stroke='{theme_colors['line_color']}' stroke-width='1'/>"
    svg += f"<line x1='{2 * column_width}' y1='{line_y1}' x2='{2 * column_width}' y2='{line_y2}' stroke='{theme_colors['line_color']}' stroke-width='1'/>"


    svg += "</svg>"
    return svg

# Generate and save SVGs for each theme
for theme_name, theme_colors in themes.items():
    svg_content = generate_themed_svg(theme_name, theme_colors)
    file_name = f"tracker-{theme_name}.svg"
    with open(file_name, "w") as f:
        f.write(svg_content)
    print(f"{file_name} generated successfully.")