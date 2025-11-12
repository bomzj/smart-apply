# Smart Apply

Smart Apply is your AI assistant that automates the process of applying to jobs directly on company websites.

It uses **LLM** to analyze websites, understand forms, and automatically:
- Fill out job application forms  
- Send emails via Gmail API 


## Setup

1. Ensure you have Python 3.12 installed. If not, download and install it from the [official Python website](https://www.python.org/).
   
2. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```
3. Install Playwright browsers:
		
    ```bash
    playwright install
    ```

#### Setup Gmail API
  
1. Create a Google Cloud project https://developers.google.com/workspace/guides/create-project#project

2. Enable Gmail API for this project https://developers.google.com/gmail/api/quickstart/python#enable_the_api

3. Configure the OAuth consent screen https://developers.google.com/gmail/api/quickstart/python#configure_the_oauth_consent_screen

4. Authorize credentials for a desktop application https://developers.google.com/gmail/api/quickstart/python#authorize_credentials_for_a_desktop_application

5. Install the Google client library https://developers.google.com/gmail/api/quickstart/python#install_the_google_client_library


## Configuration

1. Rename `.env.example` to `.env`.
2. Configure Azure OpenAI section.
> **NOTE**: Smart Apply uses Azure OpenAI by default, but it is compatible with any LLM supported by the [Smolagent](https://github.com/huggingface/smolagents) library.
3. Fill in your personal information (name, email, etc.) used during applications.
4. *Optional* Configure Langfuse for LLM tracing/debugging.

## How to use

1. Create a `urls.txt` file containing the URLs of the companies you want to apply to. 
2. Create an `applicant_message.txt` file containing the message you want to send with your applications. 
3. Run the main script:
    
```
python main.py
```