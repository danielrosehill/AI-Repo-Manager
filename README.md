# AI Repo Manager

A Linux desktop application for managing GitHub repositories with semantic search powered by OpenRouter embeddings and ChromaDB.

## Features

- **Repository Management**: View all your GitHub repositories (local and remote)
- **Semantic Search**: Find repositories using natural language queries
  - Powered by embeddings from OpenRouter
  - Results ranked by semantic similarity
  - Debounced search (500ms) for smooth typing experience
- **Incremental Sync**: Smart sync that only updates changed repositories
  - Compares `pushed_at` timestamps to detect changes
  - Only re-embeds repositories that have been modified
  - Preserves embeddings for unchanged repos between runs
- **Local Detection**: Automatically detects locally cloned repositories
- **Quick Actions**: Open in VS Code, view on GitHub, or delete local copies

## Requirements

- Python 3.11+
- Linux with X11 or Wayland
- VS Code (for "Open" functionality)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/danielrosehill/AI-Repo-Manager.git
   cd AI-Repo-Manager
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   uv venv .venv
   source .venv/bin/activate
   uv pip install -e .
   ```

3. Copy `.env.example` to `.env` and configure your API keys:
   ```bash
   cp .env.example .env
   ```

4. Edit `.env` with your credentials:
   ```bash
   GITHUB_PAT=your_github_personal_access_token
   OPENROUTER_KEY=your_openrouter_api_key
   REPOS_BASE_PATH=/path/to/your/repos
   ```

## Usage

Run the application:
```bash
source .venv/bin/activate
python -m src.main
```

Or use the installed command:
```bash
ai-repo-manager
```

### First Run

1. Click **Settings** to configure:
   - Repository base path (where your repos are cloned)
   - GitHub Personal Access Token
   - OpenRouter API Key
   - Model preferences

2. Click **Update Repos** to:
   - Fetch all repositories from GitHub
   - Generate embeddings for README content
   - Store in local vector database

3. Use the **Search bar** to:
   - Find repos by name, description, or topic (instant keyword match)
   - Search semantically with natural language (e.g., "machine learning projects")
   - See the semantic indicator showing search status

### Keyboard Shortcuts

- **Ctrl+R**: Refresh/Update repositories
- **Double-click**: Open repository in VS Code
- **Right-click**: Context menu with actions

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_PAT` | Yes | GitHub Personal Access Token |
| `OPENROUTER_KEY` | Yes | OpenRouter API Key |
| `REPOS_BASE_PATH` | No | Default path to local repositories |
| `EMBEDDING_MODEL` | No | OpenRouter embedding model (default: `openai/text-embedding-3-small`) |
| `CHAT_MODEL` | No | OpenRouter chat model (default: `anthropic/claude-sonnet-4`) |

### Storage Locations

- **Settings**: `~/.config/ai-repo-manager/settings.json`
- **Vector Store**: `~/.local/share/ai-repo-manager/chromadb/`

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     PyQt6 Main Window                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐│
│  │   Search Bar (Hybrid: Keyword + Semantic)               ││
│  │   [🔍 Search repositories...] [Public] [Private] [✨]   ││
│  ├─────────────────────────────────────────────────────────┤│
│  │   Repository List                                       ││
│  │   - Sort by date/name                                   ││
│  │   - Open in VS Code / View on GitHub                    ││
│  │   - Pagination with date headers                        ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│ GitHub API   │    │ OpenRouter API   │    │  ChromaDB    │
│ (PyGithub)   │    │ (embeddings)     │    │ (local)      │
└──────────────┘    └──────────────────┘    └──────────────┘
```

## Dependencies

- **PyQt6** - Desktop UI framework
- **PyGithub** - GitHub API client
- **ChromaDB** - Vector database for embeddings
- **httpx** - Async HTTP client for OpenRouter
- **python-dotenv** - Environment variable management

## Planned Features

- **AI Chat with RAG**: Conversational interface to ask questions about your repositories using retrieval-augmented generation

## License

MIT
