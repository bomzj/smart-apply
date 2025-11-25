# Smart Apply

Smart Apply is your AI assistant that automates the process of applying to jobs directly on company websites.

It uses **LLM** to analyze websites, understand forms, and automatically:

- Fill out job application forms

- Send emails via Gmail API

  
## Setup

### Option 1 - Without Docker (Recommended)
  
1. Ensure you have Python 3.12 installed. If not, download and install it from the [official Python website](https://www.python.org/).

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Install Camoufox stealth browser:

```bash
camoufox fetch
```

### Option 2 - With Docker
>  **NOTE**: Camoufox browser runs insanely slow(resource-heavy) in docker causing timeouts.
I tried docker optimization: increasing shared memory(/shm) from default 64MB to 2GB and writing temp files(/tmp) to RAM. Nothing helped.
```bash
docker compose build
```
> By the way Chromium is also sluggish in docker, but it more or less works, the other drawback it's detectable by anti-bot protections used on various websites.

### Setup Gmail API *(valid for both options)*

1. Create a Google Cloud project https://developers.google.com/workspace/guides/create-project#project

2. Enable Gmail API for this project https://developers.google.com/gmail/api/quickstart/python#enable_the_api

3. Configure the OAuth consent screen https://developers.google.com/gmail/api/quickstart/python#configure_the_oauth_consent_screen

4. Authorize credentials for a desktop application https://developers.google.com/gmail/api/quickstart/python#authorize_credentials_for_a_desktop_application

5. Install the Google client library https://developers.google.com/gmail/api/quickstart/python#install_the_google_client_library


## Configuration

1. Rename `.env.example` to `.env`.

2. Configure Azure OpenAI section.

>  **NOTE**: Smart Apply uses Azure OpenAI by default, but you can switch to any LLM.

3. Fill in your personal information (name, email, etc.) used during applications.

4.  *Optional* Configure Langfuse for LLM tracing/debugging.
  

## How to use

1. Create a `urls.txt` file containing the URLs of the companies you want to apply to.

2. Create an `applicant_message.txt` file containing the message you want to send with your applications.

3. Smart Apply can run **either locally or with Docker** — choose one of the options below.

```bash
python main.py
```
Or
```bash
docker compose up -d
```