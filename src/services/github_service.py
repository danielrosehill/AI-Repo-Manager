"""GitHub API service for fetching repository information."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
from typing import Generator, Callable, Optional

from github import Github, GithubException
from github.Repository import Repository as GHRepo

from ..models.repository import Repository
from .database import Database


class GitHubService:
    """Service for interacting with GitHub API."""

    def __init__(self, token: str, repos_base_path: str):
        self.github = Github(token, per_page=100)  # Max page size
        self.repos_base_path = Path(repos_base_path)

    def get_authenticated_user(self) -> str:
        """Get the authenticated user's login name."""
        return self.github.get_user().login

    def fetch_all_repos(self) -> Generator[Repository, None, None]:
        """Fetch all repositories for the authenticated user with pagination."""
        user = self.github.get_user()

        # get_repos returns a PaginatedList that handles pagination automatically
        for gh_repo in user.get_repos(sort="created", direction="desc"):
            yield self._convert_repo(gh_repo)

    def get_repo_count(self) -> int:
        """Get total repository count for the authenticated user."""
        user = self.github.get_user()
        return user.public_repos + (user.total_private_repos or 0)

    def sync_repos_to_database(
        self,
        database: Database,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        max_workers: int = 8,
    ) -> tuple[int, int]:
        """
        Sync repositories from GitHub to the local database.
        Uses parallel workers for faster processing.
        Returns (total_repos, changed_repos) count.
        """
        user = self.github.get_user()

        # Get expected total for progress reporting
        expected_total = user.public_repos + (user.total_private_repos or 0)

        if progress_callback:
            progress_callback(f"Fetching repository list from GitHub ({expected_total} expected)...", 0, 0)

        # Collect all repos first (pagination is handled by PyGithub)
        # This can take a while for large accounts
        gh_repos = []
        repos_iter = user.get_repos(sort="updated", direction="desc")
        for i, gh_repo in enumerate(repos_iter):
            gh_repos.append(gh_repo)
            if progress_callback and (i + 1) % 50 == 0:
                progress_callback(f"Fetching repository list... ({i + 1} fetched)", i + 1, expected_total)

        total = len(gh_repos)

        if progress_callback:
            progress_callback(f"Processing {total} repositories...", 0, total)

        # Check for cancellation early
        if cancel_check and cancel_check():
            return 0, 0

        # Process repos in parallel using ThreadPoolExecutor
        current = 0
        changed = 0

        def process_repo(gh_repo: GHRepo) -> dict:
            """Process a single repo - fetch topics and check local path."""
            local_path = self._find_local_path(gh_repo.name)

            # Get topics (may require extra API call)
            try:
                topics = gh_repo.get_topics()
            except GithubException:
                topics = []

            return {
                "full_name": gh_repo.full_name,
                "name": gh_repo.name,
                "description": gh_repo.description,
                "created_at": gh_repo.created_at,
                "updated_at": gh_repo.updated_at or gh_repo.created_at,
                "pushed_at": gh_repo.pushed_at or gh_repo.created_at,
                "is_private": gh_repo.private,
                "html_url": gh_repo.html_url,
                "clone_url": gh_repo.clone_url,
                "default_branch": gh_repo.default_branch or "main",
                "topics": topics,
                "local_path": str(local_path) if local_path else None,
            }

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_repo = {
                executor.submit(process_repo, gh_repo): gh_repo
                for gh_repo in gh_repos
            }

            # Process results as they complete
            for future in as_completed(future_to_repo):
                # Check for cancellation
                if cancel_check and cancel_check():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                current += 1

                try:
                    repo_data = future.result()

                    if progress_callback:
                        progress_callback(f"Syncing {repo_data['name']}...", current, total)

                    # Upsert to database - returns True if changed
                    is_changed = database.upsert_from_github(**repo_data)

                    if is_changed:
                        changed += 1

                except Exception:
                    # Skip failed repos but continue
                    pass

        # Update sync time
        database.set_last_sync_time(datetime.now())

        if progress_callback:
            progress_callback(f"Synced {current} repositories ({changed} changed)", current, current)

        return current, changed

    def _convert_repo(self, gh_repo: GHRepo) -> Repository:
        """Convert GitHub repository to our Repository model."""
        # Check if repo exists locally
        local_path = self._find_local_path(gh_repo.name)
        is_local = local_path is not None

        # Get topics
        try:
            topics = gh_repo.get_topics()
        except GithubException:
            topics = []

        return Repository(
            name=gh_repo.name,
            full_name=gh_repo.full_name,
            description=gh_repo.description,
            created_at=gh_repo.created_at,
            topics=topics,
            clone_url=gh_repo.clone_url,
            html_url=gh_repo.html_url,
            is_local=is_local,
            local_path=str(local_path) if local_path else None,
            is_private=gh_repo.private,
            default_branch=gh_repo.default_branch or "main",
        )

    def _find_local_path(self, repo_name: str) -> Path | None:
        """Check if repository exists locally."""
        if not self.repos_base_path.exists():
            return None

        # Check direct path
        direct_path = self.repos_base_path / repo_name
        if direct_path.exists() and (direct_path / ".git").exists():
            return direct_path

        return None

    def read_readme(self, repo: Repository) -> str | None:
        """Read README content for a local repository."""
        if not repo.is_local or not repo.local_path:
            return None

        local_path = Path(repo.local_path)

        # Try common README filenames
        readme_names = [
            "README.md",
            "README.MD",
            "readme.md",
            "README.rst",
            "README.txt",
            "README",
        ]

        for name in readme_names:
            readme_path = local_path / name
            if readme_path.exists():
                try:
                    return readme_path.read_text(encoding="utf-8")
                except (IOError, UnicodeDecodeError):
                    continue

        return None

    def fetch_remote_readme(self, full_name: str) -> str | None:
        """Fetch README from GitHub API."""
        try:
            gh_repo = self.github.get_repo(full_name)
            readme = gh_repo.get_readme()
            return readme.decoded_content.decode("utf-8")
        except GithubException:
            return None

    def fetch_readme_for_repo(self, repo: Repository) -> tuple[str, str | None]:
        """Fetch README for a repo (local first, then remote). Returns (full_name, readme)."""
        readme = None
        if repo.is_local and repo.local_path:
            readme = self.read_readme(repo)
        if not readme:
            readme = self.fetch_remote_readme(repo.full_name)
        return repo.full_name, readme

    def fetch_readmes_parallel(
        self,
        repos: list[Repository],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        max_workers: int = 8,
    ) -> dict[str, str]:
        """
        Fetch READMEs for multiple repos in parallel.
        Returns dict mapping full_name to readme content.
        """
        results = {}
        total = len(repos)
        current = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_repo = {
                executor.submit(self.fetch_readme_for_repo, repo): repo
                for repo in repos
            }

            for future in as_completed(future_to_repo):
                current += 1
                repo = future_to_repo[future]

                if progress_callback:
                    progress_callback(f"Fetching README for {repo.name}...", current, total)

                try:
                    full_name, readme = future.result()
                    if readme:
                        results[full_name] = readme
                except Exception:
                    pass

        return results

    def delete_local_repo(self, repo: Repository) -> bool:
        """Delete a local repository directory."""
        if not repo.is_local or not repo.local_path:
            return False

        import shutil
        try:
            shutil.rmtree(repo.local_path)
            return True
        except (IOError, OSError):
            return False

    def test_connection(self) -> tuple[bool, str]:
        """Test GitHub API connection."""
        try:
            user = self.github.get_user()
            return True, f"Connected as {user.login}"
        except GithubException as e:
            return False, f"GitHub API error: {e}"
        except Exception as e:
            return False, f"Connection error: {e}"
