# AI-Powered Resume Parsing & Skill Extraction Engine

A full-stack resume intelligence platform: upload a resume (PDF or DOCX), get
back a structured, confidence-scored `CandidateProfile` (contact,
experience, education, skills normalized against a canonical taxonomy),
and let a recruiter inspect the original source evidence for every field,
correct what's wrong, and have that correction persisted.

## Problem statement

Recruiters and applicant-tracking pipelines need structured candidate
data (skills, roles, dates, education) out of free-form resume documents,
but resumes have no fixed schema: layout varies (single-column,
multi-column, tables), headings vary or are absent entirely, and skill
names vary by alias ("JS" vs "JavaScript", "K8s" vs "Kubernetes"). A
usable system has to parse real document structure (not just flatten
text), degrade honestly when a document has nothing extractable (a scan,
an empty file) rather than fabricate data, tell a reviewer which fields
it's unsure about, and let that reviewer fix mistakes without starting
over.

## Solution overview

A modular pipeline (parse → segment → extract → normalize → score →
assemble) produces a `CandidateProfile` where every field carries its
value, a confidence score, a `needs_review` flag, and full provenance
(which section, which source block, which page, the original text) back
to the source document. A separate React review UI renders the source
evidence and the structured profile side by side, lets a recruiter edit
any field, and submits corrections through an API that validates,
applies, and persists them against the stored profile -- not just an
audit log entry.

## Architecture summary

```
Upload -> validate -> parse (PDF/DOCX) -> segment -> extract -> normalize
  -> score confidence -> assemble CandidateProfile -> persist (SQLite)
  -> Review UI (source <-> profile) -> correction API -> re-persist
```

Every stage sits behind a small interface (`ResumeParser`,
`FieldExtractor`, `CandidateRepository`, `FileStorage`) so a stage can be
swapped without touching the others. See `docs/architecture.md` for the
full diagram and per-stage detail, and `docs/TECHNICAL_REPORT.md` for the
complete writeup including validation methodology and results.

## Core pipeline

1. **Ingestion & parsing** (`parsing/`) -- pdfplumber for PDF (word-level
   bounding boxes, table detection, single/two-column reconstruction,
   scanned/image-only detection), python-docx for DOCX (true document
   order via table/paragraph interleaving, native heading styles).
2. **Segmentation** (`segmentation/segmenter.py`) -- a heading-based state
   machine (Contact / Experience / Education / Skills), with
   content-based fallbacks (date range → Experience, degree keyword →
   Education, comma-list → Skills, email/phone/URL → Contact) for
   documents with missing or nonstandard headings. Nothing is silently
   dropped -- unrecognized content goes to `UNCLASSIFIED`, never discarded.
3. **Extraction** (`extraction/`) -- deterministic regex where the format
   is structured enough (email, phone, URL, dates), curated keyword
   heuristics for job titles/companies/degrees/institutions with spaCy
   NER as a secondary supporting signal only (documented as unreliable
   alone on short fragments), and Skills-section content trusted at face
   value versus a conservative seed-list match elsewhere.
4. **Skill normalization** (`normalization/`) -- exact/alias lookup
   against a curated ~110-entry taxonomy, then fuzzy matching
   (rapidfuzz, 85/100 threshold) as a fallback; unmatched skills are kept,
   never dropped or force-matched.
5. **Confidence scoring** (`confidence/scorer.py`) -- an explainable
   engineering heuristic over the extraction evidence each field already
   carries (method used, match strength, ambiguity flags). **Not a
   calibrated probability model** -- see Confidence model below.
6. **Assembly & persistence** -- `pipeline/assembly.py` builds the
   `CandidateProfile`; `pipeline/orchestrator.py` runs the full chain
   synchronously and returns either a completed profile or a safe error
   message, never a bare exception or a fabricated result.

## Features

- PDF and DOCX ingestion with strict upload validation (extension,
  size, magic bytes)
- Table handling, two-column layout handling, scanned/image-only
  detection
- Section segmentation tolerant of missing/reordered/nonstandard headings
- Contact, experience, education, and skill extraction with full
  provenance
- Canonical skill taxonomy with alias and fuzzy normalization
- Per-field confidence scoring and `needs_review` flagging
- A recruiter review UI: source-evidence ↔ structured-profile
  comparison, per-field editing, evidence linking, a review-progress
  meter
- A correction API that validates, applies, and persists corrections
  against the real stored profile (schema-aware `field_path` whitelist,
  full-profile re-validation, audit log)
- A reproducible, hand-labeled validation harness with per-field
  precision/recall/F1

## Tech stack

- **Backend**: Python 3.12, FastAPI + Pydantic, SQLite (stdlib
  `sqlite3`) behind a repository interface, local disk file storage
- **Parsing**: pdfplumber (PDF), python-docx (DOCX)
- **NLP/matching**: spaCy (`en_core_web_sm` 3.8.0, secondary signal
  only), rapidfuzz (fuzzy skill matching)
- **Review UI**: React 18 + Vite + TypeScript, a separate app under
  `review-ui/` calling the API over JSON (see `review-ui/README.md`)
- **Quality tooling**: pytest, ruff (lint + format), pip-audit

## Setup

```bash
python3 -m pip install -e ".[dev]"
cp .env.example .env
```

`en_core_web_sm` installs automatically via the direct GitHub release URL
in `pyproject.toml`/`requirements.txt` -- no separate
`python -m spacy download` step needed.

## Running the backend

```bash
uvicorn resume_engine.api.main:app --reload
```

## Running the frontend

```bash
cd review-ui
npm install
npm run dev
```

Opens on `http://localhost:5173`, which is already in the backend's
default `RESUME_ENGINE_CORS_ALLOWED_ORIGINS`. See `review-ui/README.md`
for the UI's design concept, API integration, and known limitations.

## API overview

| Endpoint | Method | Purpose |
|---|---|---|
| `/resumes` | POST | Upload a resume; runs the full pipeline synchronously and returns `status: completed` (with `candidate_id`) or `status: failed` (safe error message) |
| `/resumes/{id}` | GET | Fetch a candidate's status, profile, and `processing_error` if any |
| `/resumes/{id}/corrections` | POST | Submit one correction; validated against a whitelist of correctable fields, applied to the stored profile, persisted, and audit-logged |
| `/health` | GET | Liveness check |

## Example flow

```bash
# 1. Upload
curl -F "file=@resume.pdf" http://localhost:8000/resumes
# -> {"candidate_id": "...", "status": "completed", ...}

# 2. Fetch the structured profile
curl http://localhost:8000/resumes/<candidate_id>

# 3. Submit a correction
curl -X POST http://localhost:8000/resumes/<candidate_id>/corrections \
  -H "Content-Type: application/json" \
  -d '{"field_path": "skills[0].canonical_name", "corrected_value": "React", "corrected_by": "recruiter@example.com"}'
# -> response includes the full updated profile and the value it replaced,
#    so a client can reflect the change without a second GET
```

`POST /resumes/{id}/corrections` validates `field_path` against an
explicit whitelist (`corrections/applier.py`) -- e.g. `contact.email.value`,
`skills[0].canonical_name`, `experience[0].company.value` -- rejects
unknown fields, out-of-range indices, and blank values, then applies the
correction to the stored `CandidateProfile`, re-validates the whole
profile, and persists it before recording the audit-log entry. A failed
validation never partially persists. The corrected field's `needs_review`
is cleared; its `confidence` is left untouched as a historical record of
the original machine read, never fabricated as a new score.

## Confidence model

`confidence/scorer.py` computes a bounded `[0.0, 1.0]` score from the
extraction evidence already captured for each field (which method
produced it, how exact the match was, whether internal signals agreed,
whether it was flagged ambiguous). A field is flagged `needs_review` when
its confidence falls below a configurable threshold (default 0.6).

**This is an explainable engineering heuristic, not a calibrated
probability model.** A score of 0.85 means "this extraction method and
match quality historically look strong by the rules in `scorer.py`" --
it does *not* mean "85% likely to be correct" in any statistical sense.
No labeled dataset was used to fit or calibrate these weights; validation
(below) checks whether `needs_review` behaves *sensibly*, not whether the
number is calibrated.

## Validation methodology

A small, reproducible, hand-labeled validation set
(`validation/ground_truth/*.json`, 10 fixtures covering PDF/DOCX,
single/multi-column, tables, missing/nonstandard headings, varied date
formats, skill aliases, and two deliberate failure cases) is scored by
`validation/evaluate.py` against the real pipeline. Matching is
deliberately strict: case-insensitive/whitespace-normalized string
comparison, no fuzzy matching, order-independent multiset matching for
repeatable fields (job titles, companies, dates, skills). See
`validation/README.md` and `docs/TECHNICAL_REPORT.md` for full
methodology, and `validation/results/summary.md` for the complete
writeup including error analysis.

**This is a 10-fixture synthetic demonstration set, not a
production-scale or statistically powered evaluation.** Every number
below describes what happened on these specific documents.

### Final metrics

| Category | Precision | Recall | F1 |
|---|---|---|---|
| Contact extraction | 0.950 | 1.000 | **0.974** |
| Experience extraction | 0.972 | 1.000 | **0.986** |
| Education extraction | 0.944 | 0.944 | **0.944** |
| Skill extraction (raw mentions) | 0.878 | 1.000 | **0.935** |

- **Overall micro F1: 0.960** · **Overall macro F1: 0.960**
- **Skill normalization accuracy: 36/36 (100%)** -- measured only over raw
  skill mentions that were themselves correctly extracted; says nothing
  about normalization of skills the extractor missed entirely.
- **Confidence sanity check** (not calibration): mean confidence of
  correct fields 0.817, of incorrect fields 0.776; **7 of 8** incorrect
  (false-positive) extractions were *not* flagged `needs_review` --
  confidence mostly reflects "was the extraction method strong," not "is
  the resulting value correct." Eight data points is too small to
  generalize a rate from, but the failure mode itself is real.
- **9 recorded errors** remain, all understood and categorized: 5
  table-header/rating-cell skill false positives (documented limitation),
  1 table-as-first-block name false positive, 1 company false positive
  from a "systems" keyword collision, 1 degree-punctuation mismatch
  (one FP + one FN, same root cause).

### One bug found and fixed during validation

Validation surfaced a genuine, previously-undocumented gap: contact
links on their own line (no email/phone on that same line, e.g. a
LinkedIn/GitHub line under the name) were never classified into the
Contact section at all, because content-based Contact detection checked
only email/phone patterns, not URLs. Fixed in
`segmentation/segmenter.py` (one additional condition, same existing
guard, four new regression tests) -- Contact category F1 improved
**0.919 → 0.974** with zero regression in any other category (confirmed
by diffing the full before/after metrics). See
`docs/TECHNICAL_REPORT.md` for the full writeup.

## Known limitations

- Confidence scoring is a documented engineering heuristic, **not**
  calibrated -- do not read a 0.85 as "85% likely correct."
- The skill taxonomy (~110 entries) is a curated starter set; niche
  technologies normalize as "unmatched" until it grows.
- Table header/rating-level cells in a Skills-section table (e.g.
  "Level", "Expert") get extracted as skill *candidates* too, since
  Skills-section content is trusted at face value; normalization
  correctly leaves these unmatched, but the extraction-stage over-capture
  itself isn't fixed (quantified in validation: 5 of 9 remaining errors).
- Job title vs. company classification relies on curated keyword lists
  plus spaCy ORG detection as a weak secondary signal; an ordinary word
  that happens to match a company-suffix keyword (e.g. "systems") can
  misclassify a whole sentence as a company (found in validation).
- Skill extraction outside the Skills section uses a curated seed list,
  not the full taxonomy -- under-recalls on niche technologies mentioned
  in prose.
- PDF column detection only distinguishes single- vs. two-column
  layouts; 3+ columns fall back to a single reading-order band.
- DOCX carries no page information without rendering.
- A correction can only be applied to a field that already has an
  extracted value -- filling in an entirely missing field is out of
  scope for this MVP's correction policy.
- Correcting one skill mention's raw text does not recompute its parent
  skill entry's entry-level `needs_review`.
- Upload is synchronous -- a large/slow file blocks the request until
  processing finishes.
- No authentication -- out of scope for this MVP.
- The validation set is small (10 fixtures) and entirely synthetic; it
  demonstrates methodology and finds real, specific bugs, but does not
  establish production-grade accuracy.

## Security & privacy notes

- **Upload validation**: extension allowlist, file-size limit, and
  magic-byte signature check, all independent of each other, before a
  file is ever written to disk or parsed (`security/upload_validation.py`).
- **Filenames**: files are stored on disk under a server-generated
  `uuid4` name, never the client-supplied name (eliminates path
  traversal/collision by construction); the original filename is kept
  only as sanitized display metadata (`security/filenames.py`).
- **Error responses** never leak stack traces, internal file paths, or
  exception details -- `api/main.py`'s generic exception handlers reshape
  every failure into a safe, stable `{code, message}` body.
- **Security headers** (`X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Cross-Origin-Resource-Policy`, and HSTS when
  deployed behind TLS) are set on every response.
- **CORS** is an explicit origin allowlist (`RESUME_ENGINE_CORS_ALLOWED_ORIGINS`),
  not a wildcard.
- **Test fixtures** are entirely synthetic (`tests/fixtures/README.md`)
  -- fake names, companies, universities; no real candidate data is used
  anywhere in this repository.
- `pip-audit` reports no known vulnerabilities in the project's runtime
  dependencies. It separately flags the local environment's `pip`
  tooling version itself as outdated -- unrelated to any code this
  project ships.
- No authentication/authorization layer exists yet; this MVP assumes a
  trusted internal deployment, per the stated scope.

## Project structure

```
src/resume_engine/
  api/            FastAPI app, routes, request/response schemas
  ingestion/      File loading
  parsing/        PDF/DOCX parsers, ParsedDocument model
  segmentation/   Section segmentation state machine
  extraction/     Per-field extractors (contact, dates, titles/companies, education, skills)
  normalization/  Skill taxonomy + normalizer
  confidence/     Confidence scoring heuristic
  corrections/    Correction application (whitelist, validation, apply)
  pipeline/       Orchestrator + CandidateProfile assembly
  schema/         CandidateProfile data contract
  persistence/    Repository interface + SQLite implementation
  storage/        File storage interface + local disk implementation
  security/       Upload validation, safe filenames
  common/         Shared regex patterns
review-ui/        React + Vite + TypeScript recruiter review app
validation/       Ground truth, evaluator, results
tests/            Unit + integration + API tests, synthetic fixtures
docs/             Architecture documentation
data/taxonomy/    Canonical skill taxonomy
scripts/          Fixture/taxonomy generation scripts
```

## Future improvements

Out of scope for this MVP, by design, until the above is complete and
validated: statistical calibration of the confidence model against a
larger labeled set, a larger/generated validation corpus, multilingual
support, duplicate-candidate detection, bias-aware extraction review,
batch/historical processing, CSV/ATS export, authentication.

