# Bounding-box focus verification

Verified on 2026-09-10 against localhost, static assets v0.5.4, using the browser UI and existing real document results. No generated documents or model calls were used.

- TCMB monetary policy decision, 17 April 2025: initial view stays at Reading size. Clicking the date box increases the rendered page width from 350 to 875 pixels (250%) and keeps the complete box visible.
- TCMB repeated percentage 46: clicking the second occurrence centers that occurrence (approximately 5 px from viewport center), rather than the first occurrence.
- TCMB decision number: selecting the finding opens the source on a narrow viewport and zooms to 250%. Resetting and clicking its source box directly also zooms and keeps the full box visible.
- NVIDIA FY2026 report: selecting Mylene Mangalindan from the entity list navigates to page 11 of 11, waits for the page image, zooms to 250%, and keeps the source box visible.
- JavaScript syntax checks passed for app.js, studio.js, refinement.js and design.js.

Implementation: each box carries its own normalized coordinates. A single final focus handler sizes the source region and centers it after layout. Pending focus is tied to the current document and page. Manual page navigation cancels it; entity discovery completion preserves an existing explicit focus.
