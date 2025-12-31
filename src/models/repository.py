"""Repository data model."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Repository:
    """Represents a GitHub repository with local and remote status."""

    name: str
    full_name: str  # owner/repo format
    description: Optional[str]
    created_at: datetime
    topics: list[str] = field(default_factory=list)
    clone_url: str = ""
    html_url: str = ""
    is_local: bool = False
    local_path: Optional[str] = None
    readme_content: Optional[str] = None
    is_embedded: bool = False
    is_private: bool = False
    default_branch: str = "main"

    def to_embedding_text(self) -> str:
        """Generate text for embedding."""
        parts = [self.name]

        if self.description:
            parts.append(self.description)

        if self.topics:
            parts.append("Topics: " + ", ".join(self.topics))

        if self.readme_content:
            # Truncate README to avoid token limits
            readme = self.readme_content[:4000]
            parts.append(readme)

        return "\n\n".join(parts)

    def to_metadata(self) -> dict:
        """Convert to metadata dict for vector store."""
        return {
            "name": self.name,
            "full_name": self.full_name,
            "description": self.description or "",
            "created_at": self.created_at.isoformat(),
            "topics": ",".join(self.topics),
            "html_url": self.html_url,
            "is_local": self.is_local,
            "local_path": self.local_path or "",
            "is_private": self.is_private,
        }

    @classmethod
    def from_metadata(cls, metadata: dict) -> "Repository":
        """Create Repository from vector store metadata."""
        topics = metadata.get("topics", "")
        topic_list = topics.split(",") if topics else []

        return cls(
            name=metadata["name"],
            full_name=metadata["full_name"],
            description=metadata.get("description") or None,
            created_at=datetime.fromisoformat(metadata["created_at"]),
            topics=topic_list,
            html_url=metadata.get("html_url", ""),
            is_local=metadata.get("is_local", False),
            local_path=metadata.get("local_path") or None,
            is_private=metadata.get("is_private", False),
            is_embedded=True,
        )
