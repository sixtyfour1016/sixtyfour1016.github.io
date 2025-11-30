# Timetable Generation Pipeline (Type-first layout)

This turns two timetable PDFs (Week A/B) into CSV → raw JSON → cleaned JSON (user rules) → ICS, then uploads ICS to Cloudflare R2. Artifacts are stored by type:
- `pdf/{user}/week_a.pdf`, `week_b.pdf`
- `csv/{user}/week_a.csv`, `week_b.csv`
- `json/{user}/raw.json` (from CSV), `json/{user}/{user}.json` (post-processed)
- `ics/{user}.ics`
- User rules: `rules/{user}.txt`
- Archives: `archive/<type>/<user>/<version>/...`

## Prerequisites
- Python 3.10+
- Install deps: `pip install -r requirements.txt` (openai, python-dotenv, boto3, etc.)
- `.env`:
  - `OPENAI_API_KEY=...`
  - R2 creds for upload: `CLOUDFLARE_ACCOUNT_ID=...`, `CLOUDFLARE_ACCESS_KEY_ID=...`, `CLOUDFLARE_SECRET_ACCESS_KEY=...`, `R2_BUCKET=...` (optional `R2_ENDPOINT=https://<account>.r2.cloudflarestorage.com`)
  - KV/API for token sync: `CLOUDFLARE_API_TOKEN=...` (KV write), `CLOUDFLARE_KV_NAMESPACE_ID=...`
  - Optional for printing links: `ICS_BASE_URL=https://your-worker.yourdomain.com`
- PDFs placed at `pdf/{user}/week_a.pdf` and `pdf/{user}/week_b.pdf` (user is dotted, e.g., `m.yang20`).
- Optional: add per-user rules in `rules/{user}.txt` (plain text instructions).

## Main pipeline (end-to-end)
Run:
```bash
python3 main.py <user> \
  [--model gpt-4.1] \
  [--prompt table_prompt.txt] \
  [--skip-pdf] [--skip-json] [--skip-post] [--skip-ics]
```
Steps executed:
1) `pdf_parser.py` → CSVs to `csv/{user}/week_a.csv` and `week_b.csv` (uses `table_prompt.txt` and GPT).
2) `csv_to_json.py` → merged `json/{user}/raw.json`.
3) `postprocess_json.py` → applies rules (from `rules/{user}.txt` or `--rules-file`); writes `json/{user}/{user}.json`. With `--copy-if-no-rules`, it will copy raw to output if no rules exist.
4) `ics.py` → generates `ics/{user}.ics` from cleaned JSON.
5) `push_to_r2.py` → uploads `ics/{user}.ics` to R2 (`ics/{user}.ics` key).

Use the skip flags to bypass steps if inputs already exist.

## Archiving before updates
Use `archive_artifacts.py` to snapshot current files to `archive/<type>/<user>/<version>/...`:
- Specific user: `python3 archive_artifacts.py m.yang20`
- All users: `python3 archive_artifacts.py --all`
- Custom version label: `python3 archive_artifacts.py m.yang20 --version v2`

## Token generation (for Worker access)
Generate per-user tokens from existing ICS files:
```bash
python3 generate_tokens.py          # text output
python3 generate_tokens.py --json   # JSON output
```
Store the tokens in Cloudflare KV (binding `TOKENS`, key=user, value=token).

## Upload helpers
- `push_to_r2.py <user>`: upload a single ICS to R2.
- `upload_and_push_r2.py`: ensure dotted ICS filenames in `ics/` and upload all to R2.
- `sync_tokens_to_kv.py --tokens <tokens.json or ics/>`: put user tokens into Cloudflare KV via API.

## User rules example
Place rules in `rules/{user}.txt`. Example (`rules/m.yang20.txt`):
```
When the subject is “Further Mathematics”, rename it according to the teacher’s surname:
Chang → Pure
Conlan → Stats
Vijayan → Mechanics
Sahota → Fun Maths
Do not keep “Mr”, “Ms”, or initials — surname only.
Keep room names exactly as shown (e.g. Sc11, Room 22, B1, etc.).
```

## Layout summary
- `pdf/{user}/week_a.pdf`, `week_b.pdf`
- `csv/{user}/week_a.csv`, `week_b.csv`
- `json/{user}/raw.json`, `json/{user}/{user}.json`
- `ics/{user}.ics`
- `rules/{user}.txt`
- `archive/<type>/<user>/<version>/...`
