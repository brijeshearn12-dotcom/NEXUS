# NEXUS — Criminal Network Analysis System
**SIH26189GREEN** | Ministry of Home Affairs (Software / Blockchain & Cybersecurity)

AI-Powered Criminal Network Analysis System for investigating organized criminal networks, multi-accused syndicates, and financial/narcotics conspiracies.

---

## Indian Kanoon API Setup & Corpus Ingestion (Task 1.1)

### 1. Configure the API Token
Acquire an API token from [Indian Kanoon API](https://api.indiankanoon.org).

Set the token in your root `.env` file (copied from `.env.example`):
```bash
INDIAN_KANOON_API_TOKEN=your_actual_token_here
```
Or export it directly in your shell session:
```powershell
# PowerShell
$env:INDIAN_KANOON_API_TOKEN="your_actual_token_here"
```
```bash
# Bash
export INDIAN_KANOON_API_TOKEN="your_actual_token_here"
```

> **Security Note:** Never commit `.env` or hardcode tokens into any script. `.env` is gitignored.

---

### 2. Run the Smoke Test
To verify your API token, network connectivity, and storage caching with a safe single-document fetch:

```powershell
# Windows PowerShell (using project virtual environment)
& .\backend\.venv\Scripts\python.exe scripts/fetch_corpus.py --smoke-test
```
Or if your venv is activated:
```bash
python scripts/fetch_corpus.py --smoke-test
```

**Expected Output:**
1. Connects to `https://api.indiankanoon.org/search/` with `Authorization: Token <token>`.
2. Searches for a sample criminal conspiracy judgment.
3. Downloads the judgment via `https://api.indiankanoon.org/doc/<tid>/`.
4. Saves raw judgment with provenance metadata into `data/raw/doc_<tid>.json`.
5. Updates `data/raw/index.json`.
6. Prints a summary report (`Successfully downloaded: 1`).

---

### 3. Fetching Real Criminal Judgment Corpora
You can fetch judgments for specific criminal topics using presets or custom queries:

```bash
# Fetch 5 judgments for Criminal Conspiracy & Multiple Accused (default preset)
python scripts/fetch_corpus.py --preset conspiracy --limit 5

# Fetch NDPS Act (Narcotics) judgments
python scripts/fetch_corpus.py --preset ndps --limit 5

# Fetch Organised Crime / Economic Offences
python scripts/fetch_corpus.py --preset organised_crime --limit 5

# Custom query
python scripts/fetch_corpus.py --query '"money laundering" conspiracy' --limit 5
```

All downloaded raw judgments are cached under `data/raw/` with provenance tracking (source URL, query, timestamp, and raw Kanoon response). Duplicate downloads are automatically skipped.
