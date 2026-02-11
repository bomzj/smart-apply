
# Smart Apply

Smart Apply is your AI assistant that automates the process of applying to jobs directly on company websites.

It uses **LLM** to analyze websites, understand forms, and automatically:
- Fill out job application forms
- Send emails via Gmail API
- Bypasses Cloudflare protection and the Google reCAPTCHA "I'm not a robot" checkbox challenge.

## Setup

### Option 1 - Without Docker (Recommended)

**Warning:** running browser under docker is pretty slow

1. Ensure you have [uv](https://docs.astral.sh/uv/) installed.

2. Install dependencies:

```bash
uv sync
```

### Option 2 - With Docker

```bash
docker compose build
```

### Setup Gmail API *(valid for both options)*

1. Create a Google Cloud project https://developers.google.com/workspace/guides/create-project#project

2. Enable Gmail API for this project https://developers.google.com/gmail/api/quickstart/python#enable_the_api

3. Configure the OAuth consent screen https://developers.google.com/gmail/api/quickstart/python#configure_the_oauth_consent_screen

4. Authorize credentials for a desktop application https://developers.google.com/gmail/api/quickstart/python#authorize_credentials_for_a_desktop_application

5. Install the Google client library https://developers.google.com/gmail/api/quickstart/python#install_the_google_client_library

*NOTE:* to renew expired gmail auth token run the following command:
```bash
uv run smart_apply/gmail.py
```

## Configuration

1. Rename `config.yaml.example` to `config.yaml`.

2. Configure `azure_openai` section.

>  **NOTE**: Smart Apply uses Azure OpenAI by default, but you can switch to any LLM.

3. Fill in your personal information (your full name, email, message, pdf resume, etc.) that will be used during job applications.

4.  *Optional* Configure Langfuse for LLM tracing/debugging.

## How to use

1. Create a `urls.txt` file containing the URLs of the companies you want to apply to.


2. Smart Apply can run **either locally or with Docker** — choose one of the options below.

```bash
uv run smart_apply/main.py
```

Or

```bash
docker compose up -d
```