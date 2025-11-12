from os import getenv
from dotenv import load_dotenv

load_dotenv()

with open("applicant_message.txt") as f:
    message = f.read()

application_template = {
    "name": getenv("APPLICANT_NAME"),
    "email": getenv("APPLICANT_EMAIL"),
    "subject": getenv("APPLICANT_SUBJECT"),
    "pdf_resume": getenv("APPLICANT_PDF"),
    "message": message.strip()
}