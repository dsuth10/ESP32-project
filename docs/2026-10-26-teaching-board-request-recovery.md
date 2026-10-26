# Teaching Board interrupted-request recovery

26 October 2026. Companion-only work on `codex/companion-media-agent`, under
the [current programme](2026-10-21-companion-media-agent-master-plan.md).
This record covers local request recovery; permanent-route deployment and
physical/classroom acceptance retain their separate gates.

## Intended workflow

An explicitly requested Board composition keeps its existing Hermes identity
through connection loss and application restart. Reopening the lesson lists
saved requests without automatically contacting Hermes or presenting a result.
The teacher can refresh an existing task, inspect its status and review a
completed page before deciding whether to present it. Completed primary-assistant
results are also recoverable locally once their output has been saved.

1. Open the same lesson through its usual Teaching Board launcher.
2. Choose the request in the **Saved Board requests** list. Running, completed,
   applied, cancelled and needs-attention outcomes remain distinguishable.
3. If needed, select **Refresh existing task**. It observes the existing Hermes
   run; an offline connection leaves the original identity and saved output intact.
4. Select **Review saved result** to inspect the complete teacher-only preview.
   Select **Present this page** only when ready. A changed lesson requires a new
   deliberate request rather than applying the old response over newer work.
5. **Cancel saved request** prevents local publication and, when available,
   requests a stop for the existing remote run. Refresh to learn its actual
   remote outcome.

Recovery never creates a replacement remote task. An uncertain dispatch without
a usable run receipt needs attention; it cannot be resubmitted from the Board
recovery controls. Cancelling prevents local publication. A remote stop request
does not establish that the remote work has ended.

The original lesson, active page, revision, content and exact resource identities
must still match before an old response can become a new preview. Opening a
lesson creates a fresh session token; recovery may rebind that token only after
the saved content passes the original-context checks. Newer or different work
remains intact. A recovered result always needs explicit preview confirmation,
including an otherwise ordinary text edit.

Publication preserves the existing one-batch Undo and Freeze behaviour. A
publication claim is retained before applying the batch so an interrupted
acknowledgement cannot make an old result publish again after restart or Undo.
Ambiguous publication requires attention rather than automatic replay.

## Local privacy and scope

Recovery records and Hermes receipts remain in the isolated local candidate
data. They are not portable lesson content, synced resources or credentials.
Editable lesson/PDF export and independent copies retain their existing explicit
allowlists. Local-only mode permits local inspection and refuses remote refresh
or stop actions. No recovery action acquires replacement images, retries a paid
provider request or changes a remote endpoint.

## Verification

Implementation: `tools/compose/board_recovery.py` owns bounded, checksummed,
atomically written local records and the interprocess publication claim.
`board_agent.py` saves the prepared selection before composition, binds Hermes
before submission and validates/rebinds recovered output through the existing
complete-page checks. `board_agent_ui.py` provides local enumeration and
background refresh/stop controls. Source-preview packaging includes the module
and this guide, while excluding private candidate records.

Independent offline verification passed **18 tests, no skips, in 2.37 seconds**:
17 cross-module recovery tests and one preview-package test. The recovery tests
use real isolated lesson/journal stores and simulated completed output; they
exercise restart/session rebinding, explicit preview, one Undo, Freeze, changed
content at an unchanged revision, unrelated-page changes, navigation, independent
lesson identity, newer edits after preview, original response-envelope checks,
cancelled/ambiguous/applied outcomes, two-window duplicate-publication rejection,
portable export privacy and independent-copy exclusion. Counts overlap the final
integrated selection and must not be added to it.

```powershell
& .local/teaching-board-renderer-env/Scripts/python.exe -m pytest tools/compose/tests/test_board_recovery_integration.py tests/test_preview_package.py -q -rs --tb=short --basetemp .local/teaching-board-candidate/pytest-request-recovery-reviewed
```

Independent review found and corrected a two-window publication race: retaining
an already-applied state alone was insufficient to stop the second window from
applying its prepared preview. The journal now grants one atomic publication
claim. Cancelled/stale/failed publication outcomes cannot be reopened by late
review updates. An interruption after claiming publication deliberately remains
ambiguous and requires attention, even if the lesson change was not saved.

The final integrated selection ran outside the filesystem sandbox with its
temporary data inside the candidate directory: **540 passed, one failed and two
skipped in 38.46 seconds**. The one failure was an existing package installation
test receiving Windows `WinError 5` at `os.replace(staging, release)`. An immediate
rerun of that complete package suite passed **18 tests, with one Windows symlink
skip, in 0.45 seconds**; no source change was made for that transient failure.
The other integrated skip was optional `pdfplumber` availability. These results
are separate evidence, not a single all-passing integrated run or additive test
counts. The Hermes service suite also passed separately: 20 tests in 2.88 seconds.

```powershell
$boardTestPaths = @(rg --files tools/compose/tests | Where-Object { $_ -match 'test_board_.*\.py$' })
& .local/teaching-board-renderer-env/Scripts/python.exe -m pytest @boardTestPaths tools/compose/tests/test_hermes_service.py tools/compose/tests/test_media_service.py tools/compose/tests/test_image_provider_routing.py tests/test_preview_package.py tests/test_companion_package.py -q -rs --tb=short --basetemp .local/teaching-board-candidate/pytest-request-recovery-final
& .local/teaching-board-renderer-env/Scripts/python.exe -m pytest tests/test_companion_package.py -q -rs --tb=short --basetemp .local/teaching-board-candidate/pytest-recovery-package-recheck
```

Earlier checks used a restricted sandbox and an unsuitable temporary directory.
Loopback/junction permissions prevented some checks; candidate reopen tests
correctly rejected data outside `.local/teaching-board-candidate/`. Repeating
the relevant checks with the required environment/directory isolated those
test-setup failures. No storage or network safeguard was weakened.

No live Hermes/provider request, network deployment, firmware write or
classroom acceptance occurred in this verification. Real connection interruption,
application relaunch with the configured service and teacher review remain
separate acceptance checks. Requests predating this journal may have unbound
Hermes receipts; those require review in the companion Hermes tasks panel and
cannot be automatically assigned to a lesson.
