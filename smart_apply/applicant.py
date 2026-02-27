from dataclasses import dataclass


@dataclass
class Applicant:
    full_name: str
    email: str
    subject: str
    pdf_resume: str
    message: str
    country: str
    company: str