import imaplib
import smtplib
from email.mime.text import MIMEText

# Replace these with your details
IMAP_SERVER = 'webmail.kth.se'
SMTP_SERVER = 'smtp.kth.se'
EMAIL_ACCOUNT = 'abe-spara-bot'
EMAIL_ADDRESS = 'spara-bot@kth.se'
PASSWORD = 'jgEAjC8#ts2sCax1ujZCn'


# Connecting to the IMAP server
imap_session = imaplib.IMAP4_SSL(IMAP_SERVER)
imap_session.login(EMAIL_ACCOUNT, PASSWORD)
print("Logged in to IMAP server successfully.")

# Select the inbox
imap_session.select('inbox')
print("Inbox selected.")

# Now, let's send an email using SMTP
smtp_session = smtplib.SMTP(SMTP_SERVER, 587)
smtp_session.ehlo()  # Can be crucial for informing the server about capabilities
smtp_session.starttls()  # Start TLS encryption
smtp_session.ehlo()  # Can be crucial for informing the server about capabilities

smtp_session.login(EMAIL_ACCOUNT, PASSWORD)

# Explicitly use PLAIN authentications
# smtp_session.login(EMAIL_ACCOUNT, PASSWORD, initial_response_ok=True)
print("Logged in to SMTP server successfully.")

# Compose an email message
message = MIMEText('This is a test message.')
message['From'] = EMAIL_ACCOUNT
message['To'] = 'oleksi@kth.se'
message['Subject'] = 'Test Email'

# Send the email
smtp_session.sendmail(EMAIL_ADDRESS, ['oleksi@kth.se'], message.as_string())
print("Test email sent successfully.")

# Logout from SMTP and IMAP
smtp_session.quit()
imap_session.logout()
