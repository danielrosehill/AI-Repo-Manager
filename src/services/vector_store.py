"""Vector store service using ChromaDB."""

from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

from ..models.repository import Repository


class VectorStore:
    """ChromaDB-based vector store for repository embeddings."""

    COLLECTION_NAME = "repositories"

    def __init__(self, persist_directory: str | Path):
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False),
        )

        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "GitHub repository embeddings"},
        )

    def upsert_repository(
        self,
        repo: Repository,
        embedding: list[float],
    ):
        """Add or update a repository in the vector store."""
        self.collection.upsert(
            ids=[repo.full_name],
            embeddings=[embedding],
            metadatas=[repo.to_metadata()],
            documents=[repo.to_embedding_text()],
        )

    def upsert_repositories_batch(
        self,
        repos: list[Repository],
        embeddings: list[list[float]],
    ):
        """Add or update multiple repositories."""
        if not repos:
            return

        self.collection.upsert(
            ids=[r.full_name for r in repos],
            embeddings=embeddings,
            metadatas=[r.to_metadata() for r in repos],
            documents=[r.to_embedding_text() for r in repos],
        )

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        where: Optional[dict] = None,
    ) -> list[tuple[Repository, float]]:
        """Query for similar repositories."""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["metadatas", "distances", "documents"],
        )

        repos_with_scores = []

        if results["metadatas"] and results["metadatas"][0]:
            metadatas = results["metadatas"][0]
            distances = results["distances"][0] if results["distances"] else [0] * len(metadatas)

            for metadata, distance in zip(metadatas, distances):
                repo = Repository.from_metadata(metadata)
                # Convert distance to similarity score (1 - distance for cosine)
                similarity = 1 - distance
                repos_with_scores.append((repo, similarity))

        return repos_with_scores

    def get_semantic_scores(
        self,
        query_embedding: list[float],
        max_results: int = 100,
    ) -> dict[str, float]:
        """
        Get semantic similarity scores for repositories.

        Returns a dict mapping full_name -> similarity_score (0-1).
        Used for hybrid search to combine with keyword matching.
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(max_results, self.count()),
            include=["distances"],
        )

        scores = {}

        if results["ids"] and results["ids"][0]:
            ids = results["ids"][0]
            distances = results["distances"][0] if results["distances"] else [0] * len(ids)

            for full_name, distance in zip(ids, distances):
                # Convert distance to similarity score (1 - distance for cosine)
                scores[full_name] = 1 - distance

        return scores

    def get_all_repositories(self) -> list[Repository]:
        """Get all repositories from the vector store."""
        results = self.collection.get(include=["metadatas"])

        repos = []
        if results["metadatas"]:
            for metadata in results["metadatas"]:
                repos.append(Repository.from_metadata(metadata))

        return repos

    def get_repository(self, full_name: str) -> Optional[Repository]:
        """Get a specific repository by full name."""
        results = self.collection.get(
            ids=[full_name],
            include=["metadatas"],
        )

        if results["metadatas"] and results["metadatas"][0]:
            return Repository.from_metadata(results["metadatas"][0])

        return None

    def delete_repository(self, full_name: str):
        """Delete a repository from the vector store."""
        try:
            self.collection.delete(ids=[full_name])
        except Exception:
            pass

    def count(self) -> int:
        """Get the number of repositories in the store."""
        return self.collection.count()

    def clear(self):
        """Clear all repositories from the store."""
        # Delete and recreate collection
        self.client.delete_collection(self.COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "GitHub repository embeddings"},
        )
