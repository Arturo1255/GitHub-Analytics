import sqlite3
import requests
import os


def database_connection():
    conn = sqlite3.connect("github_analytics.db")

    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE CONTRIBUTORS (
    CONTRIBUTOR_ID TEXT PRIMARY KEY,
    USERNAME TEXT
);

CREATE TABLE COMMITS (
    COMMIT_ID TEXT PRIMARY KEY,
    CONTRIBUTOR_ID TEXT REFERENCES contributors(contributor_id),
    COMMIT_DATE DATE,
    MESSAGE TEXT
);

CREATE TABLE ISSUES (
    ISSUE_ID TEXT PRIMARY KEY,
    ISSUE_DATE DATE,
    ISSUE_RESOLVED DATE,
    ISSUE_MESSAGE TEXT,
    CONTRIBUTOR_ID TEXT REFERENCES contributors(contributor_id) 
);
    """)

    conn.commit()
    conn.close()


def fetch_commits_page(owner: str, repo: str, page: int, token: str) -> list[dict]:
    url = "https://api.github.com/repos/" + owner + "/" + repo + "/commits"

    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json"
    }

    params = {
        "per_page": 100,
        "page": page
    }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Error occured: {e}")
        return []


def fetch_all_commits(owner: str, repo: str, token: str) -> list[dict]:
    all_commits = []
    page = 1

    while True:
        commits = fetch_commits_page(owner, repo, page, token)

        if not commits:
            break
        else:
            all_commits.extend(commits)
            page += 1

    return all_commits


def extract_commit_row(commit: dict) -> dict:
    commit_id = commit.get('sha')
    commit_date = commit.get('commit').get('author').get('date')
    commit_message = commit.get('commit').get('message')

    author = commit.get('author')

    if author is not None:
        author_id = author.get('id')
        author_username = author.get('login')
    else:
        author_id = None
        author_username = commit.get('commit').get('author').get('name')

    return {
        'commit_id': commit_id,
        'commit_date': commit_date,
        'commit_message': commit_message,
        'contributor_id': author_id,
        'username': author_username
    }


def insert_commits(conn, rows: list[dict]):
    cursor = conn.cursor()

    for row in rows:
        if row["contributor_id"] is not None:
            cursor.execute(
                "INSERT OR IGNORE INTO contributors (contributor_id, username) VALUES (?, ?)",
                (row["contributor_id"], row["username"])
            )

        cursor.execute(
            "INSERT OR IGNORE INTO commits (commit_id, contributor_id, commit_date, message) VALUES (?, ?, ?, ?)",
            (row["commit_id"], row["contributor_id"], row["commit_date"], row["commit_message"])
        )

    conn.commit()


def fetch_issues_page(owner: str, repo: str, page: int, token: str) -> list[dict]:
    url = "https://api.github.com/repos/" + owner + "/" + repo + "/issues"

    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json"
    }

    params = {
        "per_page": 100,
        "page": page
    }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Error occured: {e}")
        return []


def fetch_all_issues(owner: str, repo: str, token: str) -> list[dict]:
    all_issues = []
    page = 1

    while True:
        issues = fetch_issues_page(owner, repo, page, token)

        if not issues:
            break
        else:
            all_issues.extend(issues)
            page += 1

    return all_issues


def extract_issues_row(issue: dict) -> dict:
    if issue.get('pull_request') is None:
        issue_id = issue.get('number')
        issue_date = issue.get('created_at')
        issue_resolved = issue.get('closed_at')
        issue_message = issue.get('title')

        user = issue.get('user')

        if user is not None:
            user_id = user.get('id')
            username = user.get('login')
        else:
            user_id = None
            username = None

        return {
            "issue_id": issue_id,
            "issue_date": issue_date,
            "issue_resolved": issue_resolved,
            "issue_message": issue_message,
            "contributor_id": user_id,
            "username": username
        }

    return None


def insert_issues(conn, rows: list[dict]):
    cursor = conn.cursor()

    for row in rows:
        if row["contributor_id"] is not None:
            cursor.execute(
                "INSERT OR IGNORE INTO contributors (contributor_id, username) VALUES (?, ?)",
                (row["contributor_id"], row["username"])
            )

        cursor.execute(
            "INSERT OR IGNORE INTO issues (issue_id, ISSUE_DATE, ISSUE_RESOLVED, ISSUE_MESSAGE, CONTRIBUTOR_ID ) VALUES (?, ?, ?, ?, ?)",
            (row["issue_id"], row["issue_date"], row["issue_resolved"], row["issue_message"], row['contributor_id'])
        )

    conn.commit()


def run_pipeline(owner: str, repo: str, token: str, db_path: str = "github_analytics.db"):
    commit_data = []
    issue_data = []

    conn = sqlite3.connect(db_path)

    all_commits = fetch_all_commits(owner, repo, token)
    all_issues = fetch_all_issues(owner, repo, token)

    for commit in all_commits:
        commit_data.append(extract_commit_row(commit))

    for issue in all_issues:
        data = extract_issues_row(issue)
        if data is not None:
            issue_data.append(data)

    insert_commits(conn, commit_data)

    insert_issues(conn, issue_data)

    conn.close()


def execute_query(query: str, db_path: str = "github_analytics.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()
    return result


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # database_connection()

    # conn = sqlite3.connect("github_analytics.db")
    # cursor = conn.cursor()
    # cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    # print(cursor.fetchall())
    # conn.close()

    # token = os.environ.get("GITHUB_TOKEN")
    # run_pipeline("psf", "requests", token)

    query_top_10 = "SELECT contributors.username, COUNT(*) AS commit_count FROM commits JOIN contributors ON " \
            "commits.contributor_id = contributors.contributor_id GROUP BY contributors.username ORDER BY " \
            "commit_count DESC LIMIT 10; "

    query_null ="SELECT COUNT(*) FROM issues WHERE issue_resolved IS NULL;"

    query_avg = "SELECT AVG(julianday(issue_resolved) - julianday(issue_date)) AS avg_days_to_close FROM issues WHERE " \
                "issue_resolved IS NOT NULL; "
    print(execute_query(query_null))
    print(execute_query(query_avg))

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
