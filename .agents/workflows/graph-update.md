---
name: graph-update
description: Update the Graphify knowledge graph and rebuild all interactive HTML visualizers
---

# Workflow: /graph-update

Run this workflow to incrementally update the codebase knowledge graph and refresh all visualizers (AST-only, 0 tokens, ~1.5s).

## Steps

1. Run the update script:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\graph.ps1 update
   ```
2. Verify that `graphify-out/graph.json`, `graph.html`, `GRAPH_TREE.html`, and `ESP32-project-callflow.html` are refreshed.
3. Provide the updated node/edge stats to the user.
