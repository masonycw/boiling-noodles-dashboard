import os.path
import base64
import pandas as pd
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
# We need read-only access to emails and the ability to modify labels (to mark as read)
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# --- Configuration ---
SENDER_EMAIL = 'no-reply@reports.eats365pos.com'  # Correct Eats365 sender
SUBJECT_KEYWORD = '[TWNC000288 - 滾麵] 營業報表'
DOWNLOAD_DIR = '/home/eats365/data/交易資料'

def get_gmail_service():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None

def fetch_and_convert_reports(service, target_dir):
    try:
        # 1. Search for unread emails matching criteria
        query = f'from:{SENDER_EMAIL} subject:"{SUBJECT_KEYWORD}" is:unread has:attachment'
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])

        if not messages:
            print('No new report emails found.')
            return

        print(f'Found {len(messages)} new report emails.')

        for message in messages:
            msg_id = message['id']
            msg = service.users().messages().get(userId='me', id=msg_id).execute()
            
            # Extract date from headers for filename (optional, can also use current date)
            # headers = msg['payload']['headers']
            # date_str = next(item['value'] for item in headers if item["name"] == "Date")
            
            # 2. Find the .xls attachment
            parts = msg['payload'].get('parts', [])
            for part in parts:
                if part['filename'] and part['filename'].endswith('.xls'):
                    print(f"Found attachment: {part['filename']}")
                    
                    attachment_id = part['body'].get('attachmentId')
                    
                    # If attachmentId is not present, the data might be inline (rare for large xls)
                    if not attachment_id:
                        print("Attachment ID not found in part body, skipping.")
                        continue

                    # 3. Download the attachment data
                    attachment = service.users().messages().attachments().get(
                        userId='me', messageId=msg_id, id=attachment_id).execute()
                    
                    file_data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))

                    # 4. Save temporarily as XLS (pandas needs a file-like object or path for xls)
                    temp_xls_path = os.path.join(target_dir, part['filename'])
                    with open(temp_xls_path, 'wb') as f:
                        f.write(file_data)
                    print(f"Downloaded temporary file: {temp_xls_path}")

                    # 5. Convert to CSV using pandas
                    # Make sure target directory exists
                    os.makedirs(target_dir, exist_ok=True)
                    
                    csv_filename = part['filename'].replace('.xls', '.csv')
                    csv_path = os.path.join(target_dir, csv_filename)
                    
                    try:
                        # Required to install xlrd: pip install xlrd
                        df = pd.read_excel(temp_xls_path, engine='xlrd')
                        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
                        print(f"Successfully converted to: {csv_path}")
                        
                        # Clean up temp xls
                        os.remove(temp_xls_path)
                        print(f"Removed temporary file: {temp_xls_path}")

                        # 6. Mark email as read
                        service.users().messages().modify(
                            userId='me',
                            id=msg_id,
                            body={'removeLabelIds': ['UNREAD']}
                        ).execute()
                        print(f"Marked email {msg_id} as read.")

                    except Exception as e:
                        print(f"Error converting {temp_xls_path} to CSV: {e}")

    except HttpError as error:
         print(f'An error occurred: {error}')

if __name__ == '__main__':
    service = get_gmail_service()
    if service:
        # For deployment, save to the production directory
        fetch_and_convert_reports(service, DOWNLOAD_DIR)
