# Timetable Generation Pipeline

This repository turns two timetable PDFs (Week A/B) into a merged JSON structure, generates an `.ics` calendar, and pushes the artifacts to GitHub so they can be subscribed to as calendars.

## Contents

| File | Purpose |
| --- | --- |
| `main.py` | Orchestrates the full pipeline for a username. |
| `pdf_parser.py` | Sends a PDF + prompt to OpenAI Responses API and saves CSV output. |
| `csv_to_json.py` | Merges Week A/B CSVs into the nested JSON schema (`Week -> Day -> periods`). |
| `ics.py` | Builds an iCalendar feed from the JSON, respecting UK term dates. |
| `push_artifacts.py` | Stages `{username}_week_*.csv`, `{username}.json`, `{username}.ics`, commits, pushes, and prints the public ICS URL. |
| `table_prompt.txt` | Prompt handed to GPT so CSV output is always the same shape. |

## Prerequisites

1. **Python 3.10+** (matching the environment used for `python3`).
2. `pip install -r requirements.txt` equivalents (currently `openai`, `python-dotenv`).
3. **OpenAI API key** with access to `gpt-4.1` family—store it in `.env`:
   ```bash
   OPENAI_API_KEY=sk-...
   ```
   `pdf_parser.py` loads `.env` automatically via `python-dotenv`.
4. Put each student’s PDFs under `users/<username>/<username>_week_a.pdf` and `users/<username>_week_b.pdf`.
5. Git remote configured (e.g. GitHub). The repo should be clean before running the pipeline.

## Running the pipeline

```bash
python main.py <username> \
  [--model gpt-4.1] \
  [--prompt table_prompt.txt] \
  [--skip-pdf] [--skip-json] [--skip-ics]
```

Steps performed:

1. **PDF → CSV** (`pdf_parser.py`): uploads the PDF (`assistants` purpose), calls OpenAI Responses, and enforces the CSV header `Day,Period,Start,End,Lesson,Teacher,Room`. One call per week (`--week a/b`). Defaults to `gpt-4.1`, configurable via `--model`.
2. **CSV merge** (`csv_to_json.py`): validates headers, merges into the JSON shape expected by `ics.py`.
3. **ICS generation** (`ics.py`): iterates the school calendar from `START_DATE` → `END_DATE`, skips half-term ranges, merges double lessons, and writes `users/<username>/<username>.ics`.
4. **Git push** (`push_artifacts.py`): stages `users/<username>/{username}_week_a.csv`, `..._week_b.csv`, `...json`, `...ics`. If there are changes it commits with `Update timetable artifacts for <username>`, pushes, and prints the ICS subscription URL:
   ```
   🔗 ICS feed: webcal://sixtyfour1016.github.io/users/<username>/<username>.ics
   ```

### Notes

- Use `--skip-pdf`, `--skip-json`, or `--skip-ics` to re-run only part of the pipeline. The git push still runs, so existing artifacts are staged/committed if they changed.
- `table_prompt.txt` now includes an example row and enforces that models output the header line even if it is absent in the PDF.
- If the Responses API ever changes shape, `pdf_parser.py` contains fallbacks (`response.output`, `response.content`, `output_text`) to keep parsing robust.

## Troubleshooting

- **Missing `openai` module**: install via `python -m pip install openai`.
- **Model omits header / duplicates rows**: the parser rejects CSVs whose first row isn’t the canonical header. Adjust `table_prompt.txt` and rerun `main.py`.
- **Calendar duplicates periods**: we now consume only `response.output` to avoid double text; ensure you’re on the latest `pdf_parser.py`.
- **Push step fails**: ensure you have write access to the remote, no pre-commit hooks blocking, and the repo isn’t in a detached HEAD state.
- **ICS subscription URL**: For GitHub Pages, the HTTPS URL (`https://<user>.github.io/.../<username>.ics`) already serves `text/calendar`, so calendar apps treat it as a feed even without the `webcal://` scheme.

## Adding new students

1. Create `users/<username>/`.
2. Drop `week_a` and `week_b` PDFs in that folder.
3. Run `python main.py <username>`.
4. Share the printed ICS URL (either `webcal://...` or the HTTPS equivalent) with the student.

That’s it—the pipeline handles the rest end-to-end.
