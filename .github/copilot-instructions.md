# Copilot Instructions for Smart Apply

## 1. Project Overview
Smart Apply is an AI agent that automates job applications by navigating company websites, solving captchas, extracting contact details, and submitting forms or sending emails.
- **Stack**: Python 3.14+, Pydoll, Azure OpenAI (LLM), Gmail API.
- **Dependency Manager**: `uv`.

## 2. Architecture & Data Flow
Top-level entry point is `smart_apply/main.py`.
1. **Input**: Reads URLs from `data/urls.txt` and config from `config.yaml`.
2. **Navigation**: `main.py` iterates URLs, visiting each with Pydoll.
   - Handles Cloudflare challenges via `smart_apply/captcha_solvers/cloudflare_challenge.py`.
3. **Extraction**: `smart_apply/page_parsers.py` uses LLMs to identify career pages and extract links (ignoring specific job postings to find generic "Apply" or "Contact" pages).
4. **Application Logic**: `smart_apply/apply_methods.py` implements the strategy:
   - **Priority 1**: Direct Email, related to job application (parsed from page).
   - **Priority 2**: Form Submission, prioritizing job-related forms, then generic contact ones (detected and filled via LLM).
   - **Priority 3**: Generic Contact Email (contact@, info@, hello@).
5. **LLM Integration**: `smart_apply/llm.py` provides `ask_llm` interface to Azure OpenAI.

## 3. Important Development Workflows

- **Run Application**:
  ```bash
  uv run smart_apply/main.py
  ```
- **Run Tests**:
  ```bash
  uv run pytest
  ```
- **Dependency Management**:
  - Add packages: `uv add <package>`
  - Sync environment: `uv sync`
- **Gmail Auth**:
  - Run `uv run smart_apply/gmail.py` to refresh tokens in `secrets/`.

## 4. Key Patterns & Conventions

### LLM Usage
Do not write hardcoded regex for complex parsing. Use `ask_llm` from `smart_apply/llm.py` to interpret DOM elements or text.
```python
from llm import ask_llm
# Example: Infer company name
result = ask_llm(f"Infer company name from title: {tab.title()}")
```

### Pydoll
- Pass the `ctx` dictionary (containing browser `tab` object and applicant data) between functions to maintain browser state.

## 5. Coding Standards & Style

### Modern Python (3.14+)
- **Type Hints**: Use `X | Y` syntax (e.g., `str | None`) exclusively. Avoid `Union` or `Optional`.
- **Control Flow**: Prefer `match/case` statements over complex `if-elif` chains.

### Functional Programming
- **No OOP Logic**: Use functions for logic. Classes should only be used as `@dataclass` (structs) to hold data, without methods.
- **Pure Functions**: Prefer pure functions that take data/context as input and return new values.

### Naming Conventions
- **Minimal Prefixes**: Avoid noisy prefixes like `get_`, `is_`, `calculate_`.
  - Bad: `get_user_name()`, `is_valid()`, `calculate_total()`
  - Good: `user_name()`, `valid()`, `total()`
- **Noun-Based**: Use nouns for value retrieval functions. Use `verb_noun` only when a specific action/side-effect is primary (Haskell style).

### Style Examples
```python
from dataclasses import dataclass

# Good: Data container only, no methods
@dataclass
class JobApplication:
    company: str
    status: str | None  # Modern type hint

# Good: Functional approach with match/case
def status_message(app: JobApplication) -> str:
    match app.status:
        case "pending":
            return f"Waiting on {app.company}"
        case "rejected":
            return "Next time"
        case _:
            return "Unknown"

# Good: Noun naming (not get_company_url)
def company_url(model: JobApplication) -> str:
    return f"https://{model.company}.com"
```

## 6. Configuration & Secrets
- **Config**: Accessed via `smart_apply/config.py`. Do not hardcode API keys or model names. Use `settings.get("path.to.key")`.
- **Secrets**: `secrets/` folder contains sensitive JSONs (Gmail tokens). Never commit these.
- **Input Data**: User-specific URLs reside in `data/urls.txt`.

## 7. Docker vs Local
- **Local (Recommended)**: Faster execution. 
- **Docker**: Available via `docker-compose.yml` but explicitly noted as slower.
