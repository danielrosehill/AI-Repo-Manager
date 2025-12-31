"""Version Control System detector utility."""

from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class VCSType(Enum):
    """Supported version control systems."""
    GIT = "git"
    SUBVERSION = "svn"
    MERCURIAL = "hg"
    UNKNOWN = "unknown"


@dataclass
class VCSInfo:
    """Information about a detected VCS repository."""
    vcs_type: VCSType
    root_path: Path
    name: str
    remote_url: Optional[str] = None


def detect_vcs(path: Path) -> Optional[VCSInfo]:
    """
    Detect if a directory is a version-controlled repository.

    Args:
        path: Directory path to check

    Returns:
        VCSInfo if a VCS is detected, None otherwise
    """
    if not path.is_dir():
        return None

    # Check for Git
    git_dir = path / ".git"
    if git_dir.exists():
        remote_url = _get_git_remote(path)
        return VCSInfo(
            vcs_type=VCSType.GIT,
            root_path=path,
            name=path.name,
            remote_url=remote_url,
        )

    # Check for Subversion
    svn_dir = path / ".svn"
    if svn_dir.exists():
        return VCSInfo(
            vcs_type=VCSType.SUBVERSION,
            root_path=path,
            name=path.name,
            remote_url=_get_svn_remote(path),
        )

    # Check for Mercurial
    hg_dir = path / ".hg"
    if hg_dir.exists():
        return VCSInfo(
            vcs_type=VCSType.MERCURIAL,
            root_path=path,
            name=path.name,
            remote_url=_get_hg_remote(path),
        )

    return None


def _get_git_remote(path: Path) -> Optional[str]:
    """Get the remote URL from a Git repository."""
    try:
        config_file = path / ".git" / "config"
        if not config_file.exists():
            return None

        content = config_file.read_text()
        # Simple parsing for origin remote URL
        in_origin = False
        for line in content.splitlines():
            line = line.strip()
            if line == '[remote "origin"]':
                in_origin = True
            elif line.startswith("["):
                in_origin = False
            elif in_origin and line.startswith("url = "):
                return line[6:].strip()
    except (IOError, UnicodeDecodeError):
        pass
    return None


def _get_svn_remote(path: Path) -> Optional[str]:
    """Get the repository URL from a Subversion working copy."""
    try:
        # SVN stores info in .svn/wc.db (SQLite) in newer versions
        # or in .svn/entries in older versions
        entries_file = path / ".svn" / "entries"
        if entries_file.exists():
            content = entries_file.read_text()
            lines = content.splitlines()
            # In older SVN format, URL is typically on line 5
            if len(lines) >= 5:
                return lines[4].strip() if lines[4].strip().startswith("http") else None
    except (IOError, UnicodeDecodeError):
        pass
    return None


def _get_hg_remote(path: Path) -> Optional[str]:
    """Get the default remote URL from a Mercurial repository."""
    try:
        hgrc_file = path / ".hg" / "hgrc"
        if not hgrc_file.exists():
            return None

        content = hgrc_file.read_text()
        in_paths = False
        for line in content.splitlines():
            line = line.strip()
            if line == "[paths]":
                in_paths = True
            elif line.startswith("["):
                in_paths = False
            elif in_paths and line.startswith("default = "):
                return line[10:].strip()
    except (IOError, UnicodeDecodeError):
        pass
    return None


def scan_directory_for_repos(
    base_path: Path,
    max_depth: int = 1,
) -> list[VCSInfo]:
    """
    Scan a directory for version-controlled repositories.

    Args:
        base_path: Directory to scan
        max_depth: How deep to scan (1 = only immediate subdirectories)

    Returns:
        List of detected VCS repositories
    """
    repos = []

    if not base_path.exists() or not base_path.is_dir():
        return repos

    # Check if base_path itself is a repo
    vcs_info = detect_vcs(base_path)
    if vcs_info:
        repos.append(vcs_info)
        return repos  # Don't scan inside a repo

    # Scan subdirectories
    if max_depth > 0:
        try:
            for subdir in base_path.iterdir():
                if subdir.is_dir() and not subdir.name.startswith("."):
                    repos.extend(scan_directory_for_repos(subdir, max_depth - 1))
        except PermissionError:
            pass

    return repos


def get_readme_from_repo(repo_path: Path) -> Optional[str]:
    """
    Read README content from a repository.

    Args:
        repo_path: Path to the repository

    Returns:
        README content if found, None otherwise
    """
    readme_names = [
        "README.md",
        "README.MD",
        "readme.md",
        "README.rst",
        "README.txt",
        "README",
    ]

    for name in readme_names:
        readme_path = repo_path / name
        if readme_path.exists():
            try:
                return readme_path.read_text(encoding="utf-8")
            except (IOError, UnicodeDecodeError):
                continue

    return None


def get_description_from_repo(repo_path: Path) -> Optional[str]:
    """
    Try to get a description from the repository.
    Checks for .git/description first, then first line of README.

    Args:
        repo_path: Path to the repository

    Returns:
        Description if found, None otherwise
    """
    # Git description file
    git_desc = repo_path / ".git" / "description"
    if git_desc.exists():
        try:
            content = git_desc.read_text().strip()
            # Git default description
            if content and not content.startswith("Unnamed repository"):
                return content
        except (IOError, UnicodeDecodeError):
            pass

    # Fall back to first line of README
    readme = get_readme_from_repo(repo_path)
    if readme:
        # Skip heading markers and get first meaningful line
        for line in readme.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                # Truncate if too long
                return line[:200] if len(line) > 200 else line

    return None
