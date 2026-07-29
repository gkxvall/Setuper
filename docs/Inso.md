# Inspiration Assets

## Folder

The repository may contain an `Inso/` directory with screenshots, diagrams, terminal examples, logos, or design references.

Codex must inspect all files in `Inso/` before implementing terminal presentation, documentation visuals, branding, or a future graphical interface.

## Usage Rules

- Treat inspiration as direction, not as content to copy blindly.
- Preserve Setuper's terminal-first product identity.
- Do not copy protected logos, text, or proprietary interface assets.
- Extract reusable design principles such as spacing, hierarchy, tone, density, and interaction clarity.
- The CLI must remain usable without color, icons, or advanced terminal capabilities.
- Do not allow visual styling to reduce safety, accessibility, or machine-readable output quality.

## Expected Analysis

Before implementing visual presentation, document:

- common layout patterns;
- typography or terminal hierarchy equivalents;
- status and feedback patterns;
- applicable color roles;
- elements that are unsuitable for a CLI;
- how the inspiration translates into Rich components and plain text.

## Asset Handling

- Reference repository-relative asset paths.
- Do not embed large binaries in documentation unnecessarily.
- Optimize original Setuper assets before release.
- Record any branding decision in `decisions.md`.
