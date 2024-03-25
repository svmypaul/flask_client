# -*- coding: utf-8 -*-

import os
import flask
import requests
import json
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
from flask import render_template, session, request
from email.mime.text import MIMEText
import base64
from googleapiclient.http import MediaIoBaseUpload
from io import BytesIO
import zipfile
import logging as logger



# This variable specifies the name of a file that contains the OAuth 2.0
# information for this application, including its client_id and client_secret.
CLIENT_SECRETS_FILE = "credentials.json"

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/drive.metadata.readonly']

API_SERVICE_NAME = 'drive'
API_VERSION = 'v2'

app = flask.Flask(__name__)
# Note: A secret key is included in the sample so that it works.
# If you use this code in your application, replace this with a truly secret
# key. See https://flask.palletsprojects.com/quickstart/#sessions.
app.secret_key = 'REPLACE ME - this value is here as a placeholder.'

def create_folder(directory, folder_name):
    # Concatenate the directory path with the folder name
    folder_path = os.path.join(directory, folder_name)
    
    # Check if the folder already exists
    if not os.path.exists(folder_path):
        # Create the folder
        os.makedirs(folder_path)
        print(f"Folder '{folder_name}' created in '{directory}'.")
    else:
        print(f"Folder '{folder_name}' already exists in '{directory}'.")

@app.route('/', methods=['GET'])
def index(): 
    name = request.args.get('username')
    flask.session['username'] = name
    print(name)
    create_folder('/frelancer/resume parser/',f'{name}_drive')
    create_folder('/frelancer/resume parser/',f'{name}_mail')
    return print_index_table()


@app.route('/test')
def test_api_request():
    if 'credentials' not in flask.session:
        return flask.redirect('authorize')

    # Load credentials from the session.
    credentials = google.oauth2.credentials.Credentials(
        **flask.session['credentials'])

    drive = googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, credentials=credentials)

    files = drive.files().list().execute()

    # Save credentials back to session in case access token was refreshed.
    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    flask.session['credentials'] = credentials_to_dict(credentials)
    json_data = json.dumps(files)

    return render_template('result.html',data = json_data)

@app.route('/drive')
def drive_api_request():
    username = session.get('username', None)
    if username is not None:
        if 'credentials' not in flask.session:
            return flask.redirect('authorize')

        # Load credentials from the session.
        credentials = google.oauth2.credentials.Credentials(
            **flask.session['credentials'])

        # Build Google Drive API service
        drive = googleapiclient.discovery.build(
            'drive', 'v3', credentials=credentials)

        # Get list of files from Google Drive
        files = drive.files().list().execute()

        download_dir = f"/frelancer/resume parser/{username}_drive/"  # Change this to your desired directory

        # Iterate over each file
        for file_info in files['files']:
            file_id = file_info['id']
            file_name = file_info['name']
            logger.debug("Trying to download file_id: " + file_id + ", file_name: " + file_name)

            try:
                # Try to download the file
                request = drive.files().get_media(fileId=file_id)
                fh = open(download_dir + file_name, 'wb')
                downloader = googleapiclient.http.MediaIoBaseDownload(fh, request)

                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    print(f"Download {int(status.progress() * 100)}%.")
            except googleapiclient.errors.HttpError as e:
                # If file is not downloadable, log the error and skip downloading
                if e.resp.status == 403:
                    print(f"Skipping file_id: {file_id} - {file_name}. Reason: {e}")
                    continue
                else:
                    raise e  # Raise other HttpError exceptions

        # Save credentials back to session in case access token was refreshed.
        # ACTION ITEM: In a production app, you likely want to save these
        #              credentials in a persistent database instead.
        flask.session['credentials'] = credentials_to_dict(credentials)

        json_data = json.dumps(files)
        return flask.jsonify(**files)
    else:
        print("No Username found")

# @app.route('/hi')
# def hello():
#     username = session.get('cred', None)
#     print(username)
#     return f"<p>Hello, {username}!</p>"

# @app.route('/save')
# def save():
#     flask.session['cred'] = "save korlm"
    
#     return "<p>Hello, save!</p>"


@app.route('/authorize')
def authorize():
    # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)

    # The URI created here must exactly match one of the authorized redirect URIs
    # for the OAuth 2.0 client, which you configured in the API Console. If this
    # value doesn't match an authorized URI, you will get a 'redirect_uri_mismatch'
    # error.
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true')

    # Store the state so the callback can verify the auth server response.
    flask.session['state'] = state

    return flask.redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    state = flask.session['state']

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.request.url
    print(authorization_response)
    flow.fetch_token(authorization_response=authorization_response)

    # Store credentials in the session.
    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    credentials = flow.credentials
    flask.session['credentials'] = credentials_to_dict(credentials)

    return flask.redirect(flask.url_for('test_api_request'))


@app.route('/revoke')
def revoke():
    if 'credentials' not in flask.session:
        return ('You need to <a href="/authorize">authorize</a> before ' +
                'testing the code to revoke credentials.')

    credentials = google.oauth2.credentials.Credentials(
        **flask.session['credentials'])

    revoke = requests.post('https://oauth2.googleapis.com/revoke',
                           params={'token': credentials.token},
                           headers={'content-type': 'application/x-www-form-urlencoded'})

    status_code = getattr(revoke, 'status_code')
    if status_code == 200:
        return('Credentials successfully revoked.' + print_index_table())
    else:
        return('An error occurred.' + print_index_table())


@app.route('/clear')
def clear_credentials():
    if 'credentials' in flask.session:
        del flask.session['credentials']
    return ('Credentials have been cleared.<br><br>' +
            print_index_table())


@app.route('/send_email')
def send_email():
    if 'credentials' not in flask.session:
        return flask.redirect('authorize')

    # Load credentials from the session.
    credentials = google.oauth2.credentials.Credentials(
        **flask.session['credentials'])

    service = googleapiclient.discovery.build('gmail', 'v1', credentials=credentials)

    sender_email = "your_email@gmail.com"  # Update with your email address
    to_email = "recipient_email@example.com"  # Update with recipient's email address
    subject = "Test Email"
    message_text = "This is a test email sent from the Gmail API."

    message = MIMEText(message_text)
    message['to'] = to_email
    message['from'] = sender_email
    message['subject'] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    try:
        message = service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
        return flask.jsonify(message)
    except Exception as e:
        return f"An error occurred: {e}"
    

@app.route('/check_emails')
def check_emails():
    username = session.get('username', None)
    if username is not None:
        if 'credentials' not in flask.session:
            return flask.redirect('authorize')

        credentials = google.oauth2.credentials.Credentials(
            **flask.session['credentials'])

        service = googleapiclient.discovery.build('gmail', 'v1', credentials=credentials)

        email_data = []

        try:
            # Fetch all emails
            #response = service.users().messages().list(userId='me', q='from:(help@workindia.in)').execute()
            response = service.users().messages().list(userId='me', q='').execute()
            messages = response.get('messages', [])

            if not messages:
                return flask.jsonify([])  # Return empty list if no emails found

            # Iterate through emails
            for message in messages:
                msg = service.users().messages().get(userId='me', id=message['id']).execute()
                payload = msg['payload']
                headers = payload['headers']

                # print(payload)
                # Initialize email dictionary
                email_info = {}

                # Get email information
                email_text = ""
                for header in headers:
                    if header['name'] == 'Subject':
                        email_text += header['value'] + '\n'
                    elif header['name'] == 'From':
                        email_text += 'From: ' + header['value'] + '\n'
                email_text += '\n'

                # Check for attachments
                # parts = payload.get('parts', [])
                try:
                    for part in msg['payload'].get('parts', ''):
                    
                        if part['filename']:
                            if 'data' in part['body']:
                                data=part['body']['data']
                                #  print(data)
                            else:
                                att_id=part['body']['attachmentId']
                                att=service.users().messages().attachments().get(userId="me", messageId=message['id'],id=att_id).execute()
                                data=att['data']
                    file_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
                    path = f"{username}_mail/{part['filename']}"

                    with open(path, 'wb') as f:
                        f.write(file_data)

                except:
                    pass
                # Add email text to dictionary
                email_info['text'] = email_text

                # Add dictionary to email_data list
                email_data.append(email_info)
            print(len(email_data))
            return flask.jsonify(email_data)  # Return email data as JSON
        except Exception as e:
            return f"An error occurred: {e}"
    else:
        print("Username Not found")



def credentials_to_dict(credentials):
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}


def print_index_table():
    return ('<table>' +
            '<tr><td><a href="/test">Test an API request</a></td>' +
            '<td>Submit an API request and see a formatted JSON response. ' +
            '    Go through the authorization flow if there are no stored ' +
            '    credentials for the user.</td></tr>' +
            '<tr><td><a href="/authorize">Test the auth flow directly</a></td>' +
            '<td>Go directly to the authorization flow. If there are stored ' +
            '    credentials, you still might not be prompted to reauthorize ' +
            '    the application.</td></tr>' +
            '<tr><td><a href="/revoke">Revoke current credentials</a></td>' +
            '<td>Revoke the access token associated with the current user ' +
            '    session. After revoking credentials, if you go to the test ' +
            '    page, you should see an <code>invalid_grant</code> error.' +
            '</td></tr>' +
            '<tr><td><a href="/clear">Clear Flask session credentials</a></td>' +
            '<td>Clear the access token currently stored in the user session. ' +
            '    After clearing the token, if you <a href="/test">test the ' +
            '    API request</a> again, you should go back to the auth flow.' +
            '</td></tr>' +
            '<tr><td><a href="/send_email">Send Test Email</a></td>' +
            '<td>Send a test email using Gmail API.</td></tr></table>')


if __name__ == '__main__':
    # When running locally, disable OAuthlib's HTTPs verification.
    # ACTION ITEM for developers:
    #     When running in production *do not* leave this option enabled.
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    # Specify a hostname and port that are set as a valid redirect URI
    # for your API project in the Google API Console.
    app.run('localhost', 8080, debug=True)





