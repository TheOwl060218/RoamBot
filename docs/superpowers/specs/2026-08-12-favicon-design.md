# RoamBot Favicon Design

## Goal

Replace the browser's default globe icon with a compact RoamBot favicon. This change affects only the browser tab icon and does not alter the in-page logo, layout, or application behavior.

## Approved Direction

- Visual: minimal compass symbol.
- Shape: a thin circular outline with a simple four-point compass needle.
- Background: transparent.
- Color: one solid color at a time. Use deep teal on light browser chrome and a light neutral on dark browser chrome.
- Style: geometric and legible at 16 px, without text, gradients, shadows, or filled background blocks.

## Implementation Scope

- Add `frontend/public/favicon.svg` with a `32 32` view box.
- Add an SVG favicon link to `frontend/index.html`.
- Keep the asset self-contained with no external fonts, images, or runtime dependencies.
- Do not add app icons, web manifests, or changes to the page-level RoamBot branding.

## Verification

- Confirm the frontend production build succeeds.
- Confirm the built HTML references `/favicon.svg` and the asset is included in the build output.
- Visually confirm the compass remains recognizable in a browser tab at normal zoom in both light and dark browser themes.
- Account for favicon caching during verification by using a fresh tab or hard refresh when necessary.

## Out of Scope

- Redesigning the RoamBot logo.
- Changing colors or icons inside the application.
- Modifying backend behavior, deployment configuration, or API credentials.
