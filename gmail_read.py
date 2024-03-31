# -*- coding: utf-8 -*-

import os
import re
import flask
import requests
import json
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
from flask import render_template, session, request, make_response, jsonify,Response , redirect
from email.mime.text import MIMEText
import time
import base64
from googleapiclient.http import MediaIoBaseUpload
from io import BytesIO
import zipfile
import logging as logger
from datetime import datetime
import email.utils
from PyPDF2 import PdfReader
import pathlib
import textwrap
import json
import google.generativeai as genai
import mysql.connector
from IPython.display import display
from IPython.display import Markdown


# information for this application, including its client_id and client_secret.
CLIENT_SECRETS_FILE = "credentials.json"


SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/drive.metadata.readonly']

API_SERVICE_NAME = 'drive'
API_VERSION = 'v2'

app = flask.Flask(__name__)

app.config.update(
    SECRET_KEY='test',
    SESSION_COOKIE_SECURE=True,
)

app.secret_key = "AIzaSyCKZOEjC7op5FoDG8jeDjmo7PrChWH6E28"

mydb = mysql.connector.connect(
  host='162.241.80.15',
  user='itesfous_jobposttest',
  password='jayganesh@123',
  database='itesfous_jobposttest'
)

cursor = mydb.cursor()

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
    uniqueid = request.args.get('uniqueid')
    companyname = request.args.get('companyname')
    flask.session['username'] = name
    flask.session['uniqueid'] = uniqueid
    flask.session['companyname'] = companyname

    print(name)
    if name != None:
        create_folder('/frelancer/resume parser/',f'{name}_drive')
        create_folder('/frelancer/resume parser/',f'{name}_mail')
    # return print_index_table()
    username = session.get('username', None)
    return render_template('home.html', username = username)


@app.route('/test')
def test_api_request():
    username = session.get('username', None)
    try:
        if 'credentials' not in flask.session:
            return flask.redirect('authorize')

        # Load credentials from the session.
        credentials = google.oauth2.credentials.Credentials(
            **flask.session['credentials'])

        drive = googleapiclient.discovery.build(
            API_SERVICE_NAME, API_VERSION, credentials=credentials)

        files = drive.files().list().execute()

        # Save credentials back to session in case access token was refreshed.
 
        flask.session['credentials'] = credentials_to_dict(credentials)
        # json_data = json.dumps(files)

        return render_template('verify-mail.html', username = username)
    except Exception as e:
        print(e)
        return flask.redirect('/')

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

        flask.session['credentials'] = credentials_to_dict(credentials)

        drive_data_json = json.dumps(files)
        total_files = len(drive_data_json)

        with open(f"{username}_drive/temp.json", 'w') as json_file:
            json_file.write(drive_data_json)

        return render_template('post-drive-scan.html',number = total_files, username = username)
    else:
        print("No Username found")

## save data to database and redirect to django project
@app.route('/finaldrive')
def final_drive():
    
    username = session.get('username', None)
    
    path = f"{username}_drive"

    # Check if the path exists
    if os.path.exists(path) and os.path.isdir(path):
        # Iterate through files in the directory
        for filename in os.listdir(path):
            # Check if the file is a regular file
            if os.path.isfile(os.path.join(path, filename)):
                # Get the file extension
                _, ext = os.path.splitext(filename)
                try:
                    # If the extension is not .pdf or .docx, remove the file
                    if ext.lower() not in ['.pdf', '.docx','.json']:
                        os.remove(os.path.join(path, filename))
                        print(f"Removed {filename}")
                except:
                    pass
    else:
        print("Invalid path or path does not exist.")
    return flask.redirect('/driveparsing')


@app.route('/driveparsing')
def driveparsing():
    username = session.get('username', None)
    company_name = session.get('company_name', None)
    uniqueid = session.get('uniqueid', None)

    with open(f"{username}_drive/temp.json", 'r') as json_file:
    # Load the JSON data into a Python dictionary
        drive_info_json = json.load(json_file)
    

    if drive_info_json:
        drive_info = drive_info_json

        for i in range(len(drive_info["files"])):
            
            print(drive_info["files"][i])
            if ("name" in drive_info["files"][i]) and (".pdf" in drive_info["files"][i]["name"]):
                
                print(drive_info["files"][i]["name"])
                file_path = f"{username}_drive/{drive_info["files"][i]["name"]}"

                driveparsersave(path = file_path, jsdata = drive_info["files"][i], username = username, companyname = company_name, uniqueid = uniqueid)

                
            else:
                pass
        remove_files_in_folder(f"{username}_drive")

        ## close my sql connection
        cursor.close()
        mydb.close()
    else:
        pass
  
    return redirect("http://127.0.0.1:8000/recruiter-dashboard/")

@app.route('/authorize')
def authorize():
    # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)


    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true')

    # Store the state so the callback can verify the auth server response.
    flask.session['state'] = state

    return flask.redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():

    state = flask.session['state']

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.request.url
    print(authorization_response)
    flow.fetch_token(authorization_response=authorization_response)


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
    print(username)
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
                        email_info['subject'] = header['value'] 
                    elif header['name'] == 'From':
                        email_info['from'] =  header['value'] 
                    elif header['name'] == 'Date':
                        # Parse the date string into a datetime object
                        date_str = header['value']
                        # Parse the date string using email.utils module
                        date_tuple = email.utils.parsedate_tz(date_str)
                        if date_tuple:
                            # Convert the parsed date to a datetime object
                            received_date = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
                            # Add the received date to the email text
                            email_info['datetime'] =  received_date.strftime('%Y-%m-%d %H:%M:%S') 
                
                try:
                    for part in msg['payload'].get('parts', ''):
                    
                        if part['filename']:

                            email_info['filename'] = part['filename']  # save attachment file name

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

                email_data.append(email_info)
            print(len(email_data))

            email_data_json = json.dumps(email_data)
            with open(f"{username}_mail/temp.json", 'w') as json_file:
                json_file.write(email_data_json)

            total_email_number = len(email_data)
            addcount(value = total_email_number)
            # return flask.jsonify(email_data)  # Return email data as JSON
            return render_template('post-gmail-scan.html',number = total_email_number, username = username)
        except Exception as e:
            return f"An error occurred: {e}"
    else:
        print("Username Not found")

## save data to database and redirect to django project
@app.route('/finalgmail')
def final_gmail():
    
    username = session.get('username', None)
    
    path = f"{username}_mail"

    # Check if the path exists
    if os.path.exists(path) and os.path.isdir(path):
        # Iterate through files in the directory
        for filename in os.listdir(path):
            # Check if the file is a regular file
            if os.path.isfile(os.path.join(path, filename)):
                # Get the file extension
                _, ext = os.path.splitext(filename)
                try:
                    # If the extension is not .pdf or .docx, remove the file
                    if ext.lower() not in ['.pdf', '.docx','.json']:
                        os.remove(os.path.join(path, filename))
                        print(f"Removed {filename}")
                except:
                    pass
    else:
        print("Invalid path or path does not exist.")
    return flask.redirect('/mailparsing')


def addcount(value):
    uniqueid = flask.session['uniqueid']
    username = flask.session['username']

    select_sql = "SELECT * FROM jobpost_recruiter_login WHERE username = %s AND uniqueid = %s "
    select_val = (str(username), str(uniqueid))
    time.sleep(2)
    cursor.execute(select_sql, select_val)
    result = cursor.fetchone()  # Assuming there's only one row expected
    if result:
        no_mail = int(result[-1])   
        # Update the column value (Assuming you want to increment it by 1)
        updated_no_mail = no_mail + value
        update_sql = "UPDATE jobpost_recruiter_login SET no_email = %s WHERE username = %s AND uniqueid = %s"
        update_val = (updated_no_mail, username, uniqueid)
        time.sleep(2)
        cursor.execute(update_sql, update_val)
        time.sleep(2)
        mydb.commit()
        print("Email count successfully added.")
    

    # cursor[]

@app.route('/mailparsing')
def mailparsing():
    username = session.get('username', None)
    company_name = session.get('company_name', None)
    uniqueid = session.get('uniqueid', None)

    with open(f"{username}_mail/temp.json", 'r') as json_file:
    # Load the JSON data into a Python dictionary
        email_info_json = json.load(json_file)
    

    if email_info_json:
        email_info = email_info_json

        for i in range(len(email_info)):
            
            if ("filename" in email_info[i]) and (".pdf" in email_info[i]["filename"]):
                
                print(email_info[i]["filename"])
                file_path = f"{username}_mail/{email_info[i]["filename"]}"

                parsersave(path = file_path, jsdata = email_info[i], username = username, companyname = company_name, uniqueid = uniqueid)

                
            else:
                pass
        remove_files_in_folder(f"{username}_mail")

        ## close my sql connection
        cursor.close()
        mydb.close()
    else:
        pass
  
    return redirect("http://127.0.0.1:8000/recruiter-dashboard/")

def credentials_to_dict(credentials):
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}


# def print_index_table():
#     return ('<table>' +
#             '<tr><td><a href="/test">Test an API request</a></td>' +
#             '<td>Submit an API request and see a formatted JSON response. ' +
#             '    Go through the authorization flow if there are no stored ' +
#             '    credentials for the user.</td></tr>' +
#             '<tr><td><a href="/authorize">Test the auth flow directly</a></td>' +
#             '<td>Go directly to the authorization flow. If there are stored ' +
#             '    credentials, you still might not be prompted to reauthorize ' +
#             '    the application.</td></tr>' +
#             '<tr><td><a href="/revoke">Revoke current credentials</a></td>' +
#             '<td>Revoke the access token associated with the current user ' +
#             '    session. After revoking credentials, if you go to the test ' +
#             '    page, you should see an <code>invalid_grant</code> error.' +
#             '</td></tr>' +
#             '<tr><td><a href="/clear">Clear Flask session credentials</a></td>' +
#             '<td>Clear the access token currently stored in the user session. ' +
#             '    After clearing the token, if you <a href="/test">test the ' +
#             '    API request</a> again, you should go back to the auth flow.' +
#             '</td></tr>' +
#             '<tr><td><a href="/send_email">Send Test Email</a></td>' +
#             '<td>Send a test email using Gmail API.</td></tr></table>')

def parser(path):

    reader = PdfReader(path) 

    # Get the total number of pages in the PDF file
    num_pages = len(reader.pages)

    # Initialize an empty string to store all the extracted text
    all_text = ""

    # Iterate through all the pages
    for page_num in range(num_pages):
        # Get the page object
        page = reader.pages[page_num]
        
        # Extract text from the current page
        text = page.extract_text()
        
        # Append the extracted text to the all_text string
        all_text += text
    
    genai.configure(api_key=app.secret_key)

    model = genai.GenerativeModel('gemini-pro')
    
    question = f"{all_text} find name, skills, phone no,year of exprience, Address and email id the output should arrange it into a JSON format where the keys are 'name', 'skills', 'phone', 'yearofexp', 'address', and 'mail' "
    response = model.generate_content(question)
    # to_markdown(response.text)
    
    return response

def extract_email_address(text):
    pattern = r'[\w\.-]+@[\w\.-]+'  # Regular expression pattern for matching email addresses
    match = re.search(pattern, text)
    if match:
        return match.group()
    else:
        return None
    
def parsersave(path, jsdata, username, companyname , uniqueid):
    
    bard_response = parser(path)
    json_string = bard_response.text.replace('\n', '')
    
    try:
        print(json_string)
        json_data = json.loads(json_string)
    except:
        try:
            start_index = json_string.find('{')
            end_index = json_string.find('}', start_index) + 1

            # Extract the JSON object substring
            json_string = json_string[start_index:end_index]
            print(json_string)
            # Parse the JSON data from the extracted substring
            json_data = json.loads(json_string)
        except:
            json_data = {  "name": "",  "skills": "",  "phone": "",  "yearofexp": "",  "address": "",  "mail": ""}

    date_time = jsdata["datetime"] 
    print(date_time)
    mail = extract_email_address(jsdata["from"])
    name = json_data['name']
    heading = jsdata['subject']
    skill = json_data['skills']
    contact_no = json_data['phone']
    contact_mail = json_data['mail']
    address = json_data['address']
    recruiter_name = username
    filename = jsdata['filename']

    while True:
        try:
            sql = "INSERT INTO jobpost_gmail_cv (time, mail, name, heading, body, skill, contact_no, contact_mail, address, company_name, recruiter_name, filename, uniqueid) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            val = (date_time, str(mail), str(name), str(heading), '', str(skill), str(contact_no), str(contact_mail), str(address), str(companyname), str(recruiter_name), str(filename), str(uniqueid))

            # Check if the row already exists
            select_sql = "SELECT 1 FROM jobpost_gmail_cv WHERE mail = %s AND name = %s AND heading = %s AND uniqueid = %s"
            select_val = (str(mail), str(name), str(heading), str(uniqueid))
            time.sleep(2)
            cursor.execute(select_sql, select_val)
            existing_row = cursor.fetchone()

            if not existing_row:
                # Insert the row if it doesn't already exist
                time.sleep(3)
                cursor.execute(sql, val)
                mydb.commit()
                print("Row inserted successfully")
            else:
                print("Row already exists, skipping insertion")

            # Consume unread results
            cursor.fetchall()
            break
        except Exception as e: 
            print(e)
            time.sleep(0.2)
            pass
    # Close the cursor and connection
    # 


def driveparsersave(path, jsdata, username, companyname , uniqueid):
    
    bard_response = parser(path)
    json_string = bard_response.text.replace('\n', '')
    
    try:
        print(json_string)
        json_data = json.loads(json_string)['files']
    except:
        try:
            start_index = json_string.find('{')
            end_index = json_string.find('}', start_index) + 1

            # Extract the JSON object substring
            json_string = json_string[start_index:end_index]
            print(json_string)
            # Parse the JSON data from the extracted substring
            json_data = json.loads(json_string)
        except:
            json_data = {  "name": "",  "skills": "",  "phone": "",  "yearofexp": "",  "address": "",  "mail": ""}

    date_time = ""
    print(date_time)
    mail = "drive"
    name = json_data['name']
    heading = 'drive'
    skill = json_data['skills']
    contact_no = json_data['phone']
    contact_mail = json_data['mail']
    address = json_data['address']
    recruiter_name = username
    filename = jsdata['name']

    while True:
        try:
            sql = "INSERT INTO jobpost_gmail_cv (time, mail, name, heading, body, skill, contact_no, contact_mail, address, company_name, recruiter_name, filename, uniqueid) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            val = (date_time, str(mail), str(name), str(heading), '', str(skill), str(contact_no), str(contact_mail), str(address), str(companyname), str(recruiter_name), str(filename), str(uniqueid))

            # Check if the row already exists
            select_sql = "SELECT 1 FROM jobpost_gmail_cv WHERE mail = %s AND name = %s AND heading = %s AND uniqueid = %s"
            select_val = (str(mail), str(name), str(heading), str(uniqueid))
            time.sleep(2)
            cursor.execute(select_sql, select_val)
            existing_row = cursor.fetchone()

            if not existing_row:
                # Insert the row if it doesn't already exist
                time.sleep(3)
                cursor.execute(sql, val)
                mydb.commit()
                print("Row inserted successfully")
            else:
                print("Row already exists, skipping insertion")

            # Consume unread results
            cursor.fetchall()
            break
        except Exception as e: 
            print(e)
            time.sleep(0.2)
            pass
    # Close the cursor and connection
    # 
        

def remove_files_in_folder(folder_path):

    # Check if the folder exists
    if not os.path.exists(folder_path):
        print(f"Folder '{folder_path}' does not exist.")
        return
    
    # Iterate over all files in the folder and remove them
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
                print(f"Removed file: {file_path}")
            except Exception as e:
                print(f"Error removing file {file_path}: {e}")
              
    

if __name__ == '__main__':

    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    {app.run('localhost', 8080, debug=True)}





