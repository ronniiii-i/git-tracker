# git-tracker/generate_svg.py
import requests
import os

# This script assumes environment variables are set by the calling process (e.g., GitHub Actions)

GH_PAT = os.getenv("GH_PAT") # Renamed for consistency with setup_webhooks.py
USERNAME = os.getenv("USERNAME")

if not GH_PAT:
    print("Error: GH_PAT environment variable not set for SVG generation.")
    exit(1)
if not USERNAME:
    print("Error: USERNAME environment variable not set for SVG generation.")
    exit(1)

url = f"https://api.github.com/users/{USERNAME}/events/public" # Only public events

headers = {
    "Authorization": f"token {GH_PAT}",
    "Accept": "application/vnd.github+json" # Good practice to include Accept header
}

try:
    res = requests.get(url, headers=headers)
    res.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
    events = res.json()
except requests.exceptions.RequestException as e:
    print(f"Error fetching GitHub events: {e}")
    exit(1)

# Quick count of event types
summary = {}
for e in events:
    summary[e["type"]] = summary.get(e["type"], 0) + 1

# Sort events for consistent display
sorted_summary = sorted(summary.items(), key=lambda item: item[1], reverse=True)

# Generate SVG
# Make SVG height dynamic based on content
line_height = 20
padding_y = 10
svg_height = (len(sorted_summary) * line_height) + (2 * padding_y)
svg_width = 300 # Keep width fixed for now, or make dynamic based on text length

svg = f"<svg xmlns='http://www.w3.org/2000/svg' width='{svg_width}' height='{svg_height}'>"
svg += "<style>text { font-family: sans-serif; fill: #24292e; }</style>" # Basic styling

y = padding_y + (line_height / 2) # Starting Y position for first text element
for evt, count in sorted_summary:
    svg += f"<text x='10' y='{y}' font-size='14'>{evt}: {count}</text>"
    y += line_height
svg += "</svg>"

with open("tracker.svg", "w") as f:
    f.write(svg)

print("tracker.svg generated successfully.")