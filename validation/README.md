# Validation

A small, reproducible, hand-labeled validation set for the extraction
pipeline, plus the script that scores against it. This is a validation workflow
deliverable: it exists to produce honest precision/recall/F1 numbers for
the technical report, not to prove the extractor is production-grade.

## Structure

```
validation/
  README.md              -- this file
  ground_truth/*.json     -- one hand-labeled file per fixture, keyed by fixture filename
  evaluate.py              -- the scoring script (also see its own module docstring)
  results/
    metrics.json            -- full per-field/per-category precision/recall/F1
    errors.json             -- every individual false positive/negative/mismatch, with a reason
    summary.md               -- the human-readable writeup: dataset, methodology, findings, limitations
```

Fixtures themselves live under `tests/fixtures/` (shared with the unit
test suite) rather than duplicated here -- see `tests/fixtures/README.md`
for how they're generated. One fixture, `varied_formats_resume.pdf`, was
added specifically for this validation pass (via
`scripts/generate_test_fixtures.py`'s `make_varied_formats_resume_pdf`)
to cover contact links, month-precision dates, "Title at Company"
phrasing, an abbreviated degree, and skill aliases/taxonomy gaps -- none
of the other fixtures exercised those dimensions.

## Running it

```bash
python validation/evaluate.py
```

Runs the real `ResumeProcessingPipeline` (the same one the API uses)
against every fixture named in `ground_truth/*.json`, scores the result,
and (re)writes `results/metrics.json` and `results/errors.json`. It's
fully deterministic given the current pipeline code and fixtures.

## Ground truth format

One JSON file per fixture (e.g. `ground_truth/normal_resume_pdf.json`),
written independently from each fixture's known source text -- **never**
by reading the extractor's own output back as the "correct" answer. Each
file has `contact` (full_name/email/phone/links), `experience` (a list of
job_title/company/start_date/end_date/is_current), `education` (a list of
degree/institution/graduation_date), and `skills` (a list of
`{raw, canonical}` pairs -- `canonical: null` means the raw mention is
expected to have no taxonomy match).

## Results

See `results/summary.md` for the full writeup: dataset composition,
matching methodology, per-field and per-category precision/recall/F1,
skill normalization accuracy, a confidence sanity check (explicitly not a
calibration claim), every recurring failure category, and this
evaluation's own limitations. Headline numbers as of the last run:
overall micro F1 0.950 across 10 fixtures, with one genuine
previously-undocumented extraction gap found (contact links on their own
line are never classified into the Contact section) and reported without
being fixed, per this phase's instructions.

