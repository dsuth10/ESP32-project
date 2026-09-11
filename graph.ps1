<#
.SYNOPSIS
  Graphify Automation & Navigation Toolkit for ESP32 MacroPad Project

.DESCRIPTION
  Provides everyday commands to query, update, visualize, and watch the codebase knowledge graph.

.EXAMPLE
  .\graph.ps1 update
  .\graph.ps1 query "How does voice recording work?"
  .\graph.ps1 explain "AudioRecorder"
  .\graph.ps1 path "do_POST" "ask_hermes_gateway"
  .\graph.ps1 view
  .\graph.ps1 callflow
  .\graph.ps1 tree
  .\graph.ps1 watch
  .\graph.ps1 status
#>

param (
    [Parameter(Position = 0)]
    [string]$Command = "update",

    [Parameter(Position = 1)]
    [string]$Arg1 = "",

    [Parameter(Position = 2)]
    [string]$Arg2 = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

# Locate graphify executable
$GraphifyExe = "C:\Users\dsuth\AppData\Roaming\Python\Python313\Scripts\graphify.exe"
if (-not (Test-Path $GraphifyExe)) {
    $found = Get-Command graphify -ErrorAction SilentlyContinue
    if ($found) {
        $GraphifyExe = $found.Source
    } else {
        Write-Error "graphify executable not found! Ensure graphifyy is installed."
        exit 1
    }
}

$GraphifyOut = Join-Path $ProjectRoot "graphify-out"
$GraphJson = Join-Path $GraphifyOut "graph.json"
$GraphHtml = Join-Path $GraphifyOut "graph.html"
$CallflowHtml = Join-Path $GraphifyOut "ESP32-project-callflow.html"
$TreeHtml = Join-Path $GraphifyOut "GRAPH_TREE.html"
$ReportMd = Join-Path $GraphifyOut "GRAPH_REPORT.md"

switch ($Command.ToLower()) {
    "update" {
        Write-Host "Updating knowledge graph (AST-only, zero API cost)..." -ForegroundColor Cyan
        & $GraphifyExe update $ProjectRoot
        
        # Also update collapsible tree HTML
        & $GraphifyExe tree --output $TreeHtml 2>$null
        Write-Host "`nAll knowledge graph artifacts updated successfully in graphify-out/!" -ForegroundColor Green
    }

    "query" {
        if (-not $Arg1) {
            Write-Host "Usage: .\graph.ps1 query `"<question>`"" -ForegroundColor Yellow
            exit 1
        }
        & $GraphifyExe query $Arg1
    }

    "explain" {
        if (-not $Arg1) {
            Write-Host "Usage: .\graph.ps1 explain `"<symbol-or-concept>`"" -ForegroundColor Yellow
            exit 1
        }
        & $GraphifyExe explain $Arg1
    }

    "path" {
        if (-not $Arg1 -or -not $Arg2) {
            Write-Host "Usage: .\graph.ps1 path `"<source-symbol>`" `"<target-symbol>`"" -ForegroundColor Yellow
            exit 1
        }
        & $GraphifyExe path $Arg1 $Arg2
    }

    "view" {
        if (Test-Path $GraphHtml) {
            Write-Host "Opening interactive network visualizer: $GraphHtml" -ForegroundColor Green
            Start-Process $GraphHtml
        } else {
            Write-Warning "graph.html not found. Running .\graph.ps1 update first..."
            & $PSScriptRoot\graph.ps1 update
            Start-Process $GraphHtml
        }
    }

    "callflow" {
        if (Test-Path $CallflowHtml) {
            Write-Host "Opening Mermaid architecture callflow: $CallflowHtml" -ForegroundColor Green
            Start-Process $CallflowHtml
        } else {
            Write-Warning "Callflow HTML not found. Running export callflow-html..."
            & $GraphifyExe export callflow-html
            Start-Process $CallflowHtml
        }
    }

    "tree" {
        if (Test-Path $TreeHtml) {
            Write-Host "Opening D3 hierarchy tree: $TreeHtml" -ForegroundColor Green
            Start-Process $TreeHtml
        } else {
            Write-Warning "Tree HTML not found. Regenerating tree..."
            & $GraphifyExe tree --output $TreeHtml
            Start-Process $TreeHtml
        }
    }

    "watch" {
        Write-Host "Starting continuous file watcher. Modifying code will instantly update the graph..." -ForegroundColor Cyan
        Write-Host "Press Ctrl+C to stop watching.`n" -ForegroundColor Yellow
        & $GraphifyExe watch $ProjectRoot
    }

    "status" {
        Write-Host "=== Graphify Status ===" -ForegroundColor Cyan
        if (Test-Path $GraphJson) {
            $item = Get-Item $GraphJson
            Write-Host "Knowledge Graph : $GraphJson"
            Write-Host "Last Modified   : $($item.LastWriteTime)"
            
            # Check git commit freshness
            $gitHead = (git rev-parse --short HEAD 2>$null)
            Write-Host "Current Git HEAD: $gitHead"
            
            if (Test-Path $ReportMd) {
                Get-Content $ReportMd | Select-String -Pattern "nodes ·|Built from commit:" | ForEach-Object { Write-Host "Summary         : $_" }
            }
        } else {
            Write-Host "No graph.json found! Run .\graph.ps1 update to build." -ForegroundColor Red
        }

        # Check hook status
        $hook = Join-Path $ProjectRoot ".git\hooks\post-commit"
        if (Test-Path $hook) {
            Write-Host "Git Hook        : Active (.git/hooks/post-commit)" -ForegroundColor Green
        } else {
            Write-Host "Git Hook        : Inactive (Run .\graph.ps1 hook-install)" -ForegroundColor Yellow
        }
    }

    "hook-install" {
        Write-Host "Installing automated Git post-commit & post-checkout hooks..." -ForegroundColor Cyan
        & $GraphifyExe hook install
        Write-Host "Automated Git hooks are active." -ForegroundColor Green
    }

    default {
        Write-Host @"
Graphify Automation Toolkit:
  .\graph.ps1 update                  Re-extract AST and rebuild all visualizers (~1.5s)
  .\graph.ps1 query "<question>"      Query the knowledge graph (instant, 0 tokens)
  .\graph.ps1 explain "<symbol>"      Explain a class, function, or file and its neighbors
  .\graph.ps1 path "<from>" "<to>"    Find the shortest call/reference path between two symbols
  .\graph.ps1 view                    Open interactive D3 force network in default browser
  .\graph.ps1 callflow                Open Mermaid sequence/callflow diagram in default browser
  .\graph.ps1 tree                    Open collapsible hierarchy tree in default browser
  .\graph.ps1 watch                   Start background file watcher for live auto-updates
  .\graph.ps1 status                  Show graph stats and freshness vs git HEAD
  .\graph.ps1 hook-install            Ensure Git post-commit auto-update hook is installed
"@ -ForegroundColor Yellow
    }
}
