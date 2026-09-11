---
name: graph-query
description: Query the codebase knowledge graph for architecture and symbol relationships
---

# Workflow: /graph-query

Query the deterministic codebase knowledge graph without spending LLM tokens on reading raw source files.

## Steps

1. Run the query with the user's question:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\graph.ps1 query "<question>"
   ```
2. For specific symbols:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\graph.ps1 explain "<symbol>"
   ```
3. For call paths between two components:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\graph.ps1 path "<source>" "<target>"
   ```
4. Synthesize the findings directly for the user with file and line links.
