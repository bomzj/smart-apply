from config import settings

application_template = {
    "name": settings.applicant_name,
    "email": settings.applicant_email,
    "subject": settings.applicant_subject,
    "pdf_resume": settings.applicant_pdf,
    "message": settings.applicant_message.strip()
}
