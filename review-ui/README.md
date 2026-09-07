# Review UI

A separate React (Vite + TypeScript) app that calls the FastAPI backend
over JSON -- kept architecturally distinct from the API per the
project brief's required "review UI" / "API backend" separation.

## Design concept

**SOURCE RESUME ↔ STRUCTURED CANDIDATE PROFILE.** The workspace is a
two-pane comparison: a left "Source evidence" pane reconstructed from
every extracted field's captured provenance text (grouped by the
section segmentation assigned it), and a right "Structured profile"
pane with contact / skills / experience / education, each field
showing its confidence, its `needs_review` flag, and an evidence
disclosure that scrolls and highlights the matching block on the left.

Visual direction is a restrained, high-density, "document
intelligence" product, not a generic SaaS dashboard: a warm paper
background, a serif display face for headings against a plain sans
body face, hairline borders instead of shadows/cards-on-cards, no
gradients or glassmorphism, and a monospace face for anything that's
literally quoting the source document (evidence text, field paths).
Confidence is never color-only -- every badge carries a text label
("Needs review", "High confidence") plus the percentage.

Animation is limited to what orients the user: a 150-200ms fade for
toasts, a smooth (or instant, under `prefers-reduced-motion`) scroll
when linking a field to its source evidence. Nothing decorative.

## Workflow implemented

Upload (drag-and-drop or file picker) -> processing state -> structured
profile with confidence/needs_review indicators throughout -> inspect
source evidence per field -> edit a field -> submit a correction ->
honest success/failure feedback. A resume can also be reopened later by
candidate ID (the only lookup the API supports -- there's no
list-all-candidates endpoint).

## API integration

Calls exactly three existing endpoints (see
`../src/resume_engine/api/routes/resumes.py`), with TypeScript types in
`src/api/types.ts` hand-mirrored from `api/schemas.py` and
`schema/candidate_profile.py`:

- `POST /resumes` (multipart) -- upload; the pipeline runs
  synchronously, so the response's `status` is already `completed` or
  `failed` by the time it returns. The processing screen shown while
  this request is in flight is an honest indeterminate spinner with
  elapsed time, not a fabricated step-by-step progress bar -- the API
  doesn't report which pipeline stage it's in.
- `GET /resumes/{id}` -- fetches the full `CandidateProfile` (the
  upload response alone doesn't include it).
- `POST /resumes/{id}/corrections` -- submits one correction. Every
  `field_path` the UI sends is built internally from the profile it just
  rendered (never free-typed by the recruiter), so it always matches the
  backend's whitelist (`corrections/applier.py`); the server still
  independently validates, applies, and persists every correction. The
  response now includes the full updated `profile`, which the UI renders
  directly -- no second `GET` needed.

No new backend endpoints were added. In particular, there is no
endpoint to fetch or render the original PDF/DOCX bytes, so the "source"
pane is reconstructed from provenance text rather than a rendered
document -- see Known limitations.

## Correction behavior

Submitting a correction calls `POST /resumes/{id}/corrections`; on
success, the response's `profile` (the actual persisted, updated
`CandidateProfile`) replaces the workspace's profile state directly --
the displayed value, its cleared `needs_review` flag, and its preserved
original `confidence` all come straight from the server, not a client-side
guess. A small "Corrected by ... in this session" caption is shown for
fields corrected this session, purely informational (see
`EditableField.tsx`). A "Corrections submitted this session" log lists
every correction response returned by the API (there's no endpoint to
list past corrections, so this log itself only covers the current browser
session -- the corrections are still persisted server-side regardless).

## Running it

```bash
npm install
npm run dev       # http://localhost:5173
npm run build     # production build (tsc -b && vite build)
npm run typecheck # tsc -b --noEmit
npm test          # vitest
```

Copy `.env.example` to `.env.local` to point at a non-default API URL
(`VITE_API_BASE_URL`, default `http://localhost:8000`). The backend's
default `RESUME_ENGINE_CORS_ALLOWED_ORIGINS` already includes
`http://localhost:5173`.

## Known limitations

- **No rendered source document.** The API has no endpoint to fetch the
  original PDF/DOCX bytes, so "source evidence" is the provenance text
  every field already carries (section, page number where available,
  original text), not a rendered page. This is a deliberate scope
  boundary, not an oversight -- adding a file-serving endpoint was out
  of scope for this task.
- **A field with no extracted value can't be corrected yet.** Matches a
  documented backend policy (see the top-level README's Limitations):
  correcting through a field that was never extracted at all would mean
  synthesizing a new field with no real provenance, which the backend
  deliberately rejects (400) rather than doing silently.
- **No cross-session correction history.** There's no API to list a
  candidate's past corrections, so the correction log only reflects the
  current browser session (a page refresh loses it, though the
  corrections themselves remain in the server's audit log).
- **Skill mention text isn't independently correctable.** Only a skill
  entry's canonical name is editable (matching the PRD's own
  `skills[0].canonical_name` correction example); individual raw
  mentions are shown with their own confidence and evidence but are
  read-only.
- **No dark theme.** Light theme only; contrast was checked against
  WCAG AA in this mode only.
- **Section-nav "active" state is click-driven, not scroll-spy.** It
  reflects the last section you jumped to, not real-time scroll
  position.
- **Dev-tooling advisories, not production ones.** `npm audit` reports
  moderate/high findings in Vite's `esbuild` dev-server dependency
  chain (request-forwarding on the dev server only); this is a
  well-known, dev-server-only class of advisory across the Vite
  ecosystem and doesn't affect the production build's runtime.
