---
name: graph-visualize
description: Launch interactive architecture, call-flow, or hierarchy tree visualizers in the browser
---

# Workflow: /graph-visualize

Launch the interactive visualizations generated from the knowledge graph in the user's default web browser.

## Options

- **Network Graph (D3 Force Directed)**:
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\graph.ps1 view
  ```
- **Call-Flow Architecture (Mermaid Sequences & Pan/Zoom)**:
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\graph.ps1 callflow
  ```
- **Hierarchy Tree (Collapsible D3 Tree)**:
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\graph.ps1 tree
  ```
