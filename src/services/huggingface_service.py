"""Hugging Face API service for fetching repository information."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional

from ..models.repository import Repository
from .database import Database
from .vcs_detector import detect_vcs, get_readme_from_repo, get_description_from_repo


class HuggingFaceService:
    """Service for interacting with Hugging Face Hub API."""

    def __init__(
        self,
        token: str,
        datasets_path: str = "",
        datasets_path_2: str = "",
        models_path: str = "",
        models_path_2: str = "",
        spaces_path: str = "",
        spaces_path_2: str = "",
    ):
        self.token = token
        # Support dual path slots for each type
        self.datasets_paths = [
            Path(datasets_path) if datasets_path else None,
            Path(datasets_path_2) if datasets_path_2 else None,
        ]
        self.models_paths = [
            Path(models_path) if models_path else None,
            Path(models_path_2) if models_path_2 else None,
        ]
        self.spaces_paths = [
            Path(spaces_path) if spaces_path else None,
            Path(spaces_path_2) if spaces_path_2 else None,
        ]
        # Keep single path references for backward compatibility
        self.datasets_path = self.datasets_paths[0]
        self.models_path = self.models_paths[0]
        self.spaces_path = self.spaces_paths[0]

        self._api = None
        self._user = None

    def _get_api(self):
        """Lazy initialization of Hugging Face API client."""
        if self._api is None:
            try:
                from huggingface_hub import HfApi
                self._api = HfApi(token=self.token)
            except ImportError:
                raise ImportError(
                    "huggingface_hub is required for Hugging Face integration. "
                    "Install it with: pip install huggingface_hub"
                )
        return self._api

    def get_authenticated_user(self) -> str:
        """Get the authenticated user's username."""
        if self._user is None:
            api = self._get_api()
            user_info = api.whoami()
            self._user = user_info.get("name") or user_info.get("username", "unknown")
        return self._user

    def test_connection(self) -> tuple[bool, str]:
        """Test Hugging Face API connection."""
        try:
            username = self.get_authenticated_user()
            return True, f"Connected as {username}"
        except Exception as e:
            return False, f"Connection error: {e}"

    def _infer_privacy_from_path(self, path: Path) -> bool:
        """Infer if a repository is private based on its path containing 'private'."""
        path_str = str(path).lower()
        return "private" in path_str

    def _find_local_path(self, repo_id: str, repo_type: str) -> Optional[Path]:
        """Check if repository exists locally in configured paths."""
        # Determine which base paths to check (supports multiple path slots)
        if repo_type == "dataset":
            base_paths = [p for p in self.datasets_paths if p]
        elif repo_type == "model":
            base_paths = [p for p in self.models_paths if p]
        elif repo_type == "space":
            base_paths = [p for p in self.spaces_paths if p]
        else:
            return None

        # Extract just the repo name (without namespace)
        repo_name = repo_id.split("/")[-1] if "/" in repo_id else repo_id

        # Check all configured paths
        for base_path in base_paths:
            if not base_path.exists():
                continue

            # Check direct path
            direct_path = base_path / repo_name
            if direct_path.exists() and detect_vcs(direct_path):
                return direct_path

            # Also check with full repo_id path structure
            full_path = base_path / repo_id.replace("/", "_")
            if full_path.exists() and detect_vcs(full_path):
                return full_path

        return None

    def sync_repos_to_database(
        self,
        database: Database,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        max_workers: int = 8,
    ) -> tuple[int, int]:
        """
        Sync repositories from Hugging Face to the local database.
        Returns (total_repos, new_repos) count.
        """
        api = self._get_api()
        username = self.get_authenticated_user()

        all_repos = []

        # Fetch datasets
        if self.datasets_path:
            if progress_callback:
                progress_callback("Fetching datasets from Hugging Face...", 0, 0)

            try:
                datasets = list(api.list_datasets(author=username))
                for ds in datasets:
                    all_repos.append(("dataset", ds))
            except Exception:
                pass

        # Fetch models
        if self.models_path:
            if progress_callback:
                progress_callback("Fetching models from Hugging Face...", 0, 0)

            try:
                models = list(api.list_models(author=username))
                for model in models:
                    all_repos.append(("model", model))
            except Exception:
                pass

        # Fetch spaces
        if self.spaces_path:
            if progress_callback:
                progress_callback("Fetching spaces from Hugging Face...", 0, 0)

            try:
                spaces = list(api.list_spaces(author=username))
                for space in spaces:
                    all_repos.append(("space", space))
            except Exception:
                pass

        total = len(all_repos)
        if progress_callback:
            progress_callback(f"Processing {total} Hugging Face repositories...", 0, total)

        if cancel_check and cancel_check():
            return 0, 0

        current = 0
        new_repos = 0

        def process_repo(repo_type: str, repo_info) -> dict:
            """Process a single HF repo."""
            repo_id = repo_info.id
            local_path = self._find_local_path(repo_id, repo_type)

            # Infer privacy from path
            is_private = False
            if local_path:
                is_private = self._infer_privacy_from_path(local_path)
            elif hasattr(repo_info, "private"):
                is_private = repo_info.private

            # Get created/updated times
            created_at = getattr(repo_info, "created_at", None) or datetime.now()
            last_modified = getattr(repo_info, "last_modified", None) or created_at

            # Build HTML URL
            if repo_type == "dataset":
                html_url = f"https://huggingface.co/datasets/{repo_id}"
            elif repo_type == "space":
                html_url = f"https://huggingface.co/spaces/{repo_id}"
            else:
                html_url = f"https://huggingface.co/{repo_id}"

            # Get tags as topics
            tags = getattr(repo_info, "tags", []) or []

            return {
                "full_name": f"hf:{repo_type}:{repo_id}",
                "name": repo_id.split("/")[-1] if "/" in repo_id else repo_id,
                "description": getattr(repo_info, "description", None),
                "local_path": str(local_path) if local_path else None,
                "is_private": is_private,
                "source": "huggingface",
                "source_subtype": repo_type,
                "topics": tags[:10],  # Limit tags
                "html_url": html_url,
                "created_at": created_at,
                "last_modified": last_modified,
            }

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_repo = {
                executor.submit(process_repo, repo_type, repo_info): (repo_type, repo_info)
                for repo_type, repo_info in all_repos
            }

            for future in as_completed(future_to_repo):
                if cancel_check and cancel_check():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                current += 1

                try:
                    repo_data = future.result()

                    if progress_callback:
                        progress_callback(f"Syncing {repo_data['name']}...", current, total)

                    # Upsert to database
                    is_new = database.upsert_local_repo(
                        full_name=repo_data["full_name"],
                        name=repo_data["name"],
                        description=repo_data["description"],
                        local_path=repo_data["local_path"] or "",
                        is_private=repo_data["is_private"],
                        source=repo_data["source"],
                        source_subtype=repo_data["source_subtype"],
                        topics=repo_data["topics"],
                        html_url=repo_data["html_url"],
                    )

                    if is_new:
                        new_repos += 1

                except Exception:
                    pass

        if progress_callback:
            progress_callback(f"Synced {current} HF repositories ({new_repos} new)", current, current)

        return current, new_repos

    def fetch_readme_for_repo(self, repo: Repository) -> tuple[str, Optional[str]]:
        """Fetch README for a repo (local first, then remote). Returns (full_name, readme)."""
        readme = None

        # Try local first
        if repo.local_path:
            readme = get_readme_from_repo(Path(repo.local_path))

        # Fall back to HF API
        if not readme and repo.source_subtype:
            try:
                api = self._get_api()
                # Extract repo_id from full_name (hf:type:owner/name)
                parts = repo.full_name.split(":")
                if len(parts) >= 3:
                    repo_id = parts[2]
                    repo_type = parts[1]

                    try:
                        readme = api.model_info(repo_id).card_data
                        if hasattr(readme, "get"):
                            readme = readme.get("description", "")
                    except Exception:
                        pass
            except Exception:
                pass

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


class LocalRepoService:
    """Service for scanning and syncing local repositories."""

    def __init__(self, base_path: str, source_name: str = "work"):
        self.base_path = Path(base_path) if base_path else None
        self.source_name = source_name

    def sync_repos_to_database(
        self,
        database: Database,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> tuple[int, int]:
        """
        Scan local directory and sync repositories to database.
        Returns (total_repos, new_repos) count.
        """
        if not self.base_path or not self.base_path.exists():
            return 0, 0

        if progress_callback:
            progress_callback(f"Scanning {self.base_path} for repositories...", 0, 0)

        # Find all VCS repos
        from .vcs_detector import scan_directory_for_repos

        repos = scan_directory_for_repos(self.base_path, max_depth=2)
        total = len(repos)

        if progress_callback:
            progress_callback(f"Found {total} repositories in {self.source_name}", 0, total)

        if cancel_check and cancel_check():
            return 0, 0

        current = 0
        new_repos = 0

        for vcs_info in repos:
            if cancel_check and cancel_check():
                break

            current += 1

            # Generate a unique full_name
            full_name = f"{self.source_name}:{vcs_info.name}"

            # Infer privacy from path
            is_private = "private" in str(vcs_info.root_path).lower()

            # Get description from repo
            description = get_description_from_repo(vcs_info.root_path)

            if progress_callback:
                progress_callback(f"Syncing {vcs_info.name}...", current, total)

            # Upsert to database
            is_new = database.upsert_local_repo(
                full_name=full_name,
                name=vcs_info.name,
                description=description,
                local_path=str(vcs_info.root_path),
                is_private=is_private,
                source=self.source_name,
                source_subtype=vcs_info.vcs_type.value,
            )

            if is_new:
                new_repos += 1

        if progress_callback:
            progress_callback(f"Synced {current} repos from {self.source_name} ({new_repos} new)", current, current)

        return current, new_repos

    def fetch_readme_for_repo(self, repo: Repository) -> tuple[str, Optional[str]]:
        """Fetch README for a local repo. Returns (full_name, readme)."""
        readme = None
        if repo.local_path:
            readme = get_readme_from_repo(Path(repo.local_path))
        return repo.full_name, readme

    def fetch_readmes_parallel(
        self,
        repos: list[Repository],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        max_workers: int = 8,
    ) -> dict[str, str]:
        """Fetch READMEs for multiple local repos in parallel."""
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
                    progress_callback(f"Reading README for {repo.name}...", current, total)

                try:
                    full_name, readme = future.result()
                    if readme:
                        results[full_name] = readme
                except Exception:
                    pass

        return results
