# git-tracker/setup_webhooks.py
from github import Github
from github import GithubException
import os
from dotenv import load_dotenv

# Load environment variables (useful for local testing)
load_dotenv()

GH_PAT = os.getenv("GH_PAT")
TRACKER_REPO = os.getenv("TRACKER_REPO")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://github-activity-hook.onrender.com/webhook")

if not GH_PAT:
    print("Error: GH_PAT environment variable not set.")
    exit(1)
if not TRACKER_REPO:
    print("Error: TRACKER_REPO environment variable not set.")
    exit(1)
if not WEBHOOK_SECRET:
    print("Warning: WEBHOOK_SECRET environment variable not set. Webhooks will not be secured.")


gh = Github(GH_PAT)
try:
    user = gh.get_user()
    print(f"Authenticated as: {user.login}")
except GithubException as e:
    print(f"Error authenticating with GitHub: {e}")
    print("Please check your GH_PAT and its permissions (especially 'repo' scope).")
    exit(1)

# --- CRITICAL CHANGE HERE ---
# Fetch only repositories owned by the authenticated user
# 'owner' type includes repositories owned by the authenticated user.
# Other types include 'all', 'public', 'private', 'member', 'organization'.
print(f"Fetching only user-owned repositories (excluding {TRACKER_REPO})...")
try:
    user_repos = user.get_repos(type='owner')
except GithubException as e:
    print(f"Error fetching user-owned repositories: {e}")
    print("Please ensure your GH_PAT has sufficient permissions (e.g., 'repo' scope).")
    exit(1)
# --- END CRITICAL CHANGE ---


for repo in user_repos: # Now iterating over the filtered list
    if repo.name == TRACKER_REPO:
        continue  # Skip the tracker repo itself

    try:
        hooks = repo.get_hooks()
        already_hooked = any(h.config.get("url") == WEBHOOK_URL for h in hooks)

        if already_hooked:
            print(f"✅ {repo.name} already hooked with {WEBHOOK_URL}")
            continue

        print(f"Attempting to add hook to {repo.name}...")
        repo.create_hook(
            name="web",
            config={
                "url": WEBHOOK_URL,
                "content_type": "json",
                "secret": WEBHOOK_SECRET
            },
            events=["push", "pull_request", "issues", "issue_comment"],
            active=True
        )
        print(f"🎯 Hook added to {repo.name}")
    except GithubException as e:
        print(f"❌ Failed to process hooks for {repo.name}: {e}")
        print(f"   Possible cause: Insufficient permissions for '{repo.name}' or repository not found.")
    except Exception as e:
        print(f"❌ An unexpected error occurred while processing {repo.name}: {e}")

print("\nWebhook setup process complete.")