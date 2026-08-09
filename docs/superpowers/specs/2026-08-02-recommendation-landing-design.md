# Recommendation Landing Design

## Goal

After a successful recommendation, keep the current query and its edit action visible before the user begins reading candidate details. Avoid a large blank band between the query summary and the results.

## Interaction

1. Keep the full form visible while the recommendation request and initial downward movement complete.
2. Replace the full form with the compact current-query summary.
3. Smoothly settle the viewport with the summary card 16 px below the sticky header.
4. Show the results heading immediately below the summary card.
5. Keep the existing smooth upward transition when the user selects `修改条件`.

No additional floating edit button, instructional toast, or duplicate edit action is introduced.

## Layout

- Desktop gap between the query summary and results: 20 px.
- Mobile gap between the query summary and results: 12 px.
- Do not reserve viewport-height space between the two sections.
- The landing viewport should show the complete query summary, the `修改条件` action, and the beginning of the results whenever the viewport height permits.

## Implementation Boundary

- Reuse `SearchWorkspace`, `QuerySummary`, and the existing scrolling helper.
- Change only the post-submit landing target and spacing needed for this behavior.
- Do not change recommendation data, scoring, candidate selection, or API behavior.

## Acceptance Criteria

- Submitting a valid query visibly moves toward the result area without an abrupt jump.
- The final resting position starts at the compact query summary, not inside candidate details.
- `修改条件` is visible at the landing position.
- The query summary and results are separated by a compact, consistent gap on desktop and mobile.
- Editing conditions still expands the form and scrolls upward smoothly.
