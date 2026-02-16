import requests
import json

def github_skills(username):
    languages = set()
    source_count = 0
    fork_count = 0
    page = 1
    
    while True:
        url = f"https://api.github.com/users/{username}/repos?per_page=100&page={page}"
        print(f"Fetching {url}...")
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            break
        
        repos = response.json()
        if not repos:
            break
            
        for repo in repos:
            if repo.get("fork"):
                fork_count += 1
            else:
                source_count += 1
                
            lang = repo.get("language")
            if lang:
                languages.add(lang.lower())
        
        if len(repos) < 100:
            break
        page += 1

    return list(languages), source_count, fork_count

if __name__ == "__main__":
    # Using a known user with many repos and forks for testing
    # e.g., 'torvalds' (though he might not have many repos on his own profile, but he has forks)
    # Let's try 'google' (orgs work too) or a known active user.
    # Actually, let's just test with 'torvalds' to see.
    username = "torvalds"
    langs, sources, forks = github_skills(username)
    print(f"User: {username}")
    print(f"Languages: {langs}")
    print(f"Source Repos: {sources}")
    print(f"Forked Repos: {forks}")
