# Sales collateral

Two leave-behinds, both editable in source control.

## `one_pager.html` — the front-door sales sheet

Single-page, print-styled HTML matched to the live site brand
(`app/templates/public/landing.html`). Open in any browser and either:

- Print → physical leave-behind for site visits.
- File → Save as PDF → email attachment.

Letter size, 0.4" margins, fits on one page. No build step.

**When to send it:** first-touch email, before any meeting, or as a leave-behind
after a site walk. Generic enough to drop in front of any prospect without
customization.

## `proposal_template.md` — the per-prospect proposal

Customized after a site visit. Fill in the `{{ placeholders }}` (or
let Claude do it from a sales record). Convert to PDF via
`pandoc proposal_template.md -o proposal.pdf` or just paste into a Doc.

The appendix at the bottom is a quick reference for which field comes from
which system. Don't strip it until the final send.

**Workflow:**

1. Site visit complete, terms discussed.
2. Copy `proposal_template.md` to `docs/sales/proposals/<host>-<date>.md`
   (the `proposals/` folder is gitignored to keep prospect data out of the repo).
3. Fill in placeholders.
4. Export to PDF, send.
5. Once signed, the placement agreement (separate document, TBD) is what
   actually binds the parties.

## Open work

- [ ] Phone number to put in the footer (placeholder `__________` for now).
- [ ] Settle the standard commission terms (0% vs 10%) before locking down
      the proposal default.
- [ ] Build the separate one-page Placement Agreement that the proposal
      promises (Research Tracker 5.6).
- [ ] Add a `proposals/` folder gitignore once the workflow is in use.
- [ ] Optional: a `/sales/print` route in the app that serves the
      one-pager with the live equipment photos pulled from `app/static/images/`.
