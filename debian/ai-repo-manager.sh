#!/bin/bash
# AI Repo Manager launcher
# User data is preserved in:
#   - ~/.config/ai-repo-manager/ (settings)
#   - ~/.local/share/ai-repo-manager/ (vector database)

exec /opt/ai-repo-manager/bin/python -m src.main "$@"
