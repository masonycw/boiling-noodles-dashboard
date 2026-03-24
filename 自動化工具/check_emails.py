import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None

def check_recent_emails(service):
    try:
        # Search for any recent emails with attachments
        query = 'has:attachment'
        results = service.users().messages().list(userId='me', q=query, maxResults=10).execute()
        messages = results.get('messages', [])

        if not messages:
            print('No emails found.')
            return

        print('Recent emails with attachments:')
        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            headers = msg['payload']['headers']
            
            subject = 'N/A'
            sender = 'N/A'
            
            for header in headers:
                if header['name'] == 'Subject':
                    subject = header['value']
                if header['name'] == 'From':
                    sender = header['value']
                    
            print(f"- From: {sender}\n  Subject: {subject}\n")

    except HttpError as error:
         print(f'An error occurred: {error}')

if __name__ == '__main__':
    service = get_gmail_service()
    if service:
        check_recent_emails(service)
