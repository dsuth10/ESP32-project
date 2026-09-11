---
name: graphify-toolkit
description: Complete toolset and automation cheatsheet for querying, updating, and visualizing the Graphify knowledge graph for this ESP32 MacroPad and Voice Satellite project.
---

# Graphify Toolkit & Automation System

This skill provides everyday workflows for maintaining and interacting with the codebase knowledge graph in `graphify-out/`.

## Automated Background Updating

The project is configured with three distinct automated layers to keep the graph 100% fresh without manual effort:

### 1. Git Commit Hook (Zero-Touch)
- **Location**: `.git/hooks/post-commit` and `.git/hooks/post-checkout`
- **Behavior**: Every time `git commit` or `git checkout` runs, the hook automatically detects changed files and executes an incremental AST update in ~1.5s in the background.
- **Verification**: Run `.\graph.ps1 status` to see if the hook is active and whether the graph matches the current Git HEAD.

### 2. Live File Watcher (Continuous Auto-Update on Save)
- **Command**: `powershell -ExecutionPolicy Bypass -File .\graph.ps1 watch`
- **Behavior**: Monitors `src/`, `server/`, `docs/` in real-time. Whenever any file is saved in the editor, Graphify immediately re-extracts the AST and updates `graph.json` and the HTML visualizers in milliseconds.

### 3. Antigravity Agent Rule (Automated Turn-End Maintenance)
- **Rule**: `.agents/rules/graphify.md`
- **Behavior**: Whenever Antigravity finishes editing code in a session, it executes `graphify update .` so the knowledge graph is always current before answering subsequent queries.

---

## Everyday Command Reference (`.\graph.ps1`)

| Command | Action | Output / Behavior |
| :--- | :--- | :--- |
| `.\graph.ps1 update` | Incremental AST update | Rebuilds `graph.json`, `graph.html`, `ESP32-project-callflow.html`, `GRAPH_TREE.html` (~1.5s) |
| `.\graph.ps1 query "<question>"` | Knowledge graph query | Traverses call/symbol graph; returns scoped nodes & connections |
| `.\graph.ps1 explain "<symbol>"` | Explain component | Details inbound/outbound relationships, degree, and defining file |
| `.\graph.ps1 path "<A>" "<B>"` | Find shortest path | Traces call sequences from symbol A to symbol B |
| `.\graph.ps1 view` | Open interactive graph | Launches `graphify-out\graph.html` in default browser |
| `.\graph.ps1 callflow` | Open call-flow diagram | Launches `graphify-out\ESP32-project-callflow.html` with Mermaid sequence |
| `.\graph.ps1 tree` | Open hierarchy tree | Launches `graphify-out\GRAPH_TREE.html` with collapsible D3 tree |
| `.\graph.ps1 watch` | Start live watcher | Continuous auto-update on every file save |
| `.\graph.ps1 status` | Freshness check | Compares graph commit vs git HEAD and checks git hook status |
| `.\graph.ps1 hook-install` | Install git hooks | Ensures `.git/hooks/post-commit` is active |

---

## Slash Commands in Antigravity Chat

You can type these directly in the chat:
- `/graph-update`: Run an immediate refresh of all graph artifacts.
- `/graph-query`: Query the graph for architecture questions.
- `/graph-visualize`: Open visualizers in the browser.
- `/graphify`: Full Graphify pipeline.
