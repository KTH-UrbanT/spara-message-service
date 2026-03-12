import email
from email.header import decode_header
from datetime import datetime
import imaplib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class Email:
    def __init__(self, id, subject, body, attachments, is_threaded, thread_id, sender, recipient, timestamp):
        self.id = id
        self.subject = subject
        self.body = body
        self.attachments = attachments or []
        self.isThreaded = is_threaded
        self.threadId = thread_id
        self.sender = sender
        self.recipient = recipient
        self.timestamp = timestamp

    @staticmethod
    def decode_header_part(header_part):
        decoded_parts = decode_header(header_part)
        header, encoding = decoded_parts[0]
        if isinstance(header, bytes):
            return header.decode(encoding or 'utf-8', errors='ignore')
        return header

    @classmethod
    def from_imap(cls, raw_email_bytes, email_id):
        msg = email.message_from_bytes(raw_email_bytes)

        subject = cls.decode_header_part(msg.get("Subject"))
        sender = msg.get("From")
        recipient = msg.get("To")
        date_str = msg.get("Date")
        timestamp = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z') if date_str else None

        body = ""
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = part.get("Content-Disposition")
                if part.get_content_type() == "text/plain" and "attachment" not in str(content_disposition):
                    body = part.get_payload(decode=True).decode(errors="ignore")
                elif "attachment" in str(content_disposition):
                    filename = part.get_filename()
                    attachments.append(filename)
        else:
            body = msg.get_payload(decode=True).decode(errors="ignore")

        thread_id = msg.get("In-Reply-To") or msg.get("References") or None
        is_threaded = bool(thread_id)

        return cls(
            id=email_id,
            subject=subject,
            body=body,
            attachments=attachments,
            is_threaded=is_threaded,
            thread_id=thread_id,
            sender=sender,
            recipient=recipient,
            timestamp=timestamp
        )

    def mark_as_read(self, imap_session):
        imap_session.store(self.id, '+FLAGS', '\\Seen')

    def send_email(self, smtp_session, from_email, to_email):
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = self.subject

        msg.attach(MIMEText(self.body, 'plain'))
        smtp_session.sendmail(from_email, to_email, msg.as_string())
