import base64, json, os, time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import mimetypes
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.credentials import TokenState
from google.oauth2.credentials import Credentials

# Gmail API scopes, we need to send emails only
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# Secrets are relative to project root
SECRETS_DIR = "secrets"
TOKEN_PATH = os.path.join(SECRETS_DIR, 'token.json')
CREDS_PATH = os.path.join(SECRETS_DIR, 'credentials.json')

def auth():
    """Authenticate with Gmail API and return credentials"""
    creds = None
    
    # Check if token.json exists with stored credentials
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_info(
            json.loads(open(TOKEN_PATH).read())
        )
    
    # If credentials don't exist or are invalid, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next run
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    
    return creds

def create_message(sender, to, subject, body, attachments=None):
    """Create email message with optional attachments
    
    Args:
        sender (str): Email sender
        to (str): Email recipient
        subject (str): Email subject
        body (str): Email body content
        attachments (list): Optional list of attachment file paths
        
    Returns:
        dict: Gmail API message object
    """
    # Create multipart message
    message = MIMEMultipart()
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    
    # Add body to email
    message.attach(MIMEText(body))
    
    # Process attachments if provided
    if attachments:
        for file_path in attachments:
            if not os.path.isfile(file_path):
                from smart_apply.logger import log_warning
                log_warning(f"Attachment not found - {file_path}")
                continue
                
            # Guess the content type based on the file extension
            content_type, encoding = mimetypes.guess_type(file_path)
            
            if content_type is None or encoding is not None:
                # If type cannot be guessed, use a generic type
                content_type = 'application/octet-stream'
                
            main_type, sub_type = content_type.split('/', 1)
            
            with open(file_path, 'rb') as fp:
                # Create attachment
                attachment = MIMEBase(main_type, sub_type)
                attachment.set_payload(fp.read())
                
                # Encode attachment in base64
                encoders.encode_base64(attachment)
                
                # Add header with the filename
                filename = os.path.basename(file_path)
                attachment.add_header('Content-Disposition', 'attachment', filename=filename)
                message.attach(attachment)
    
    # Encode message as URL-safe base64 string
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}


# After Gmail authentication our credentials will be stored here
creds = None
service = None
last_send_time = 0

# TODO: Refactor not to use global variables e.g. gmail_sender() -> send_email_from_me()
def send_email_from_me(to, subject, body, attachments=None):
    """ Send email via Gmail API.\n
    Note:
        Personal Gmail has limit of 500 emails/day.
        Per user rate limit is 15000 quota units/min. 
        So 15000 / 60 / 100 = 2.5 messages per second in theory
        based on https://developers.google.com/workspace/gmail/api/reference/quota
    """
    global creds, service, last_send_time

    # Throttling: Enforce at least 10 seconds between sends to stay under 6 messages/min (very conservative)
    time_since_last  = time.time() - last_send_time
    if time_since_last < 10:
        time.sleep(10 - time_since_last)
    
    # Authenticate and build service if not already fresh/valid
    if not creds or creds.token_state != TokenState.FRESH:
        creds = auth()
        service = build('gmail', 'v1', credentials=creds)
    
    # Special value indicating the authenticated user to avoid emails being flagged with warning 
    sender = "me"

    email = create_message(sender, to, subject, body, attachments)
    
    res = service.users().messages().send(
        userId=sender, body=email).execute()
    last_send_time = time.time()
    return res


# To renew token.json only (no email sent)
if __name__ == '__main__':
    # Delete token.json if it exists to force fresh authentication
    if os.path.exists(TOKEN_PATH):
        os.remove(TOKEN_PATH)
        print("Deleted existing token.json to force re-authentication.")
        
    creds = auth()
    print("Authentication successful! New token.json created.")