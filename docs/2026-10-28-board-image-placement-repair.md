# Plain image placement repair

28 October 2026, companion feature branch.

A dog photograph was retrieved and saved, but the composition model omitted
`schema`, used `type` instead of `op` for the command and supplied an incomplete
image object with an unsupported caption field. Strict validation correctly
retained the existing pupil page. The saved request nevertheless displayed
`completed`, referring to the model response rather than successful publication.

Plain single-image requests on an empty page now use typed application-owned
image placement, preserving proportions and the exact source credit. This avoids
asking a second model to construct Board commands. Complex briefs and pages with
existing content retain the normal composition route, with additional command
and envelope guidance. A single eligible cached image match can be selected
directly; multiple matches still require a choice. Generated images retain their
first-use preview requirement, and the normal image, layout and publication
validation remains in force.

Validation failures retain the original response and record that the page was
not presented. Saved-response labels distinguish presentation from response
completion. Refresh is disabled when there is no unfinished remote task.

The exact reported failure was reproduced, and the saved dog/photo/credit replay
passed the native layout check before the user requested testing to stop. Testing
and UI submission stopped at that request. Final changes, including single-match
cached selection, have not been rerun or manually accepted. The user will test
after closing and reopening the application. No claim of pupil presentation,
classroom acceptance, deployment or release is made by this commit.

The existing photo remains saved locally; no replacement paid image was requested.
