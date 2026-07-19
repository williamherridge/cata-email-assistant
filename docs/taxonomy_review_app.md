# Taxonomy Review App

This local web app helps review taxonomy discovery samples.

## What It Does

- Loads taxonomy discovery runs from `data/analytics/taxonomy_discovery/`
- Displays the sampled messages for quick review
- Lets you fill in:
  - `approved_category`
  - `approved_subcategory`
  - `review_notes`
- Saves edits back to the run's `*_sample.json`
- Maintains a shared taxonomy catalog in `data/analytics/taxonomy_catalog.json`
- Supports normalization by renaming a category or subcategory across the loaded sample
- Lets you promote reviewed labels from a run into the shared catalog

## Run It

From repo root:

```bash
python scripts/taxonomy_review_app.py
```

Then open:

```text
http://127.0.0.1:8008
```

Optional host/port:

```bash
python scripts/taxonomy_review_app.py --host 127.0.0.1 --port 8010
```

## Suggested Workflow

1. Load a discovery run.
2. Filter to `Unreviewed`.
3. Skim and assign category/subcategory values.
4. Reuse existing category chips when possible.
5. Use `Normalize Labels` to merge near-duplicate labels.
6. Save periodically. Saving now also updates the shared taxonomy catalog.
7. Use `Promote reviewed labels` if you want to force a full re-promotion from the loaded run.

## Notes

- The app edits the `*_sample.json` for the selected run.
- The shared canonical category list is stored in `data/analytics/taxonomy_catalog.json`.
- `Save changes` updates both the run sample and the shared taxonomy catalog.
- It does not modify the original cleaned email files.
- Each taxonomy discovery run already lives in its own timestamped directory, so your review passes remain separate.
