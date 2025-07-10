from flask import Flask, redirect, url_for, session, request, render_template, send_file
from authlib.integrations.flask_client import OAuth
import boto3
import os
import uuid
import datetime
import json
import csv
from io import BytesIO

# ====================
# SECURITY WARNING
# ====================
# Hardcoding credentials is a significant security risk.
# In a real-world application, use environment variables or AWS IAM roles.
# For example:
# ais = {
#     'access_key': os.environ.get('AWS_ACCESS_KEY_ID'),
#     'secret_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
#     'region': os.environ.get('AWS_REGION')
# }
# ====================

# ====================
# Flask App Setup
# ====================

appliacation = Flask(__name__)
application = appliacation
application.secret_key = "wowuowrjwer9023r239h9j"

# ====================
# AWS & Cognito Config
# ====================
ais = {
    'access_key': 'AKIA6FIQDWZWJOPKXKHE',
    'secret_key': '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',
    'region': 'eu-north-1'
}
USER_POOL_ID = "eu-north-1_8nOgsOGhF"
CLIENT_ID    = "53loo229e76aj0kq99rqlu33ea"
CLIENT_SECRET= "1h5540a3siu47d8bhee6onerk6734j7l0tlfr6s6elf4hqfb2dej"
COG_DOMAIN   = f"https://cognito-idp.{ais['region']}.amazonaws.com/{USER_POOL_ID}"

# ====================
# DynamoDB Tables
# ====================
try:
    dynamo = boto3.resource(
        'dynamodb',
        region_name=ais['region'],
        aws_access_key_id=ais['access_key'],
        aws_secret_access_key=ais['secret_key']
    )
    synth_tbl = dynamo.Table("SyntheticData")
    fb_tbl    = dynamo.Table("Feedback")
except Exception as e:
    print(f"FATAL: Could not connect to DynamoDB. Check credentials and region. Error: {e}")
    # Exit or handle gracefully if you cannot connect
    dynamo, synth_tbl, fb_tbl = None, None, None

# ====================
# OAuth (Authlib + Cognito Hosted UI)
# ====================
oauth = OAuth(application)
oauth.register(
    name='oidc',
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    server_metadata_url=f"{COG_DOMAIN}/.well-known/openid-configuration",
    client_kwargs={'scope': 'openid email phone'}
)

# ====================
# Routes
# ====================
@application.route('/')
def home():
    return redirect(url_for('generate'))

# -------- Auth --------
@application.route('/login')
def login():
    return oauth.oidc.authorize_redirect(redirect_uri="http://localhost:5001/authorize")

@application.route('/authorize')
def authorize():
    token = oauth.oidc.authorize_access_token()
    session['user'] = token.get('userinfo', {})
    return redirect(url_for('generate'))

@application.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('logout_confirm'))

@application.route('/logout_confirm')
def logout_confirm():
    return render_template('logout_confirm.html')

# -------- Generate Synthetic Data --------
@application.route('/generate', methods=['GET','POST'])
def generate():
    user = session.get('user')
    email = user.get('email') if user else 'guest@example.com'
    is_guest = not user
    
    record_id = None
    preview = ''
    error_message = None

    if request.method == 'POST':
        file = request.files.get('file')
        
        if not file or file.filename == '':
            error_message = "Please upload a CSV schema file."
        else:
            try:
                csv_bytes = file.read()
                csv_lines = csv_bytes.decode('utf-8').splitlines()
                header = csv_lines[0].split(',')

                domain = request.form['domain']
                count  = int(request.form['count'])
                noise  = float(request.form['noise'])
                balance= 'balance' in request.form
                mask   = 'mask_pii' in request.form

                # --- This is the placeholder for your actual synthetic data logic ---
                synthetic = []
                for i in range(1, count + 1):
                    rec = {col.strip(): f"{col.strip()}_{i}" for col in header}
                    synthetic.append(rec)
                # --- End of placeholder logic ---

                output = StringIO()
                writer = csv.DictWriter(output, fieldnames=header)
                writer.writeheader()
                writer.writerows(synthetic)
                csv_output = output.getvalue()
                preview = '\n'.join(csv_output.splitlines()[:10])
                record_id = str(uuid.uuid4())
                
                if synth_tbl:
                    synth_tbl.put_item(Item={
                        'SynteticData': record_id,
                        'email': email,
                        'domain': domain,
                        'prompt': json.dumps({'domain':domain,'count':count,'noise':noise,'balance':balance,'mask_pii':mask}),
                        'sample': csv_output,
                        'created_at': datetime.datetime.utcnow().isoformat(),
                        'is_guest': is_guest
                    })

            except Exception as e:
                error_message = f"An error occurred: {e}"

    return render_template('generate.html', user=user, is_guest=is_guest, record_id=record_id, preview=preview, error_message=error_message)

# -------- Agent Assistant --------
@application.route('/agent', methods=['POST'])
def agent():
    query = request.form.get('query', '').lower()
    response = ""
    if 'noise' in query:
        response = "Noise controls how much randomness is added to your synthetic data. 0 means very clean, 1 means very random."
    elif 'balance' in query:
        response = "Balancing classes ensures all categories in your dataset appear equally. Useful for training ML models."
    elif 'pii' in query or 'mask' in query:
        response = "Masking PII hides sensitive personal information like names or phone numbers in the generated data."
    elif 'records' in query or 'how many' in query:
        response = "You can generate up to 1000 records per request. The more records, the more realistic your sample."
    elif 'role' in query or 'columns' in query:
        response = "Roles/Columns refer to the fields/headers in your CSV input. They determine what type of data is generated."
    else:
        response = "Sorry, I'm not sure how to answer that. Try asking about noise, balance, PII, records or columns."
    
    return render_template('agent.html', response=response)

# -------- View My Data --------
@application.route('/view')
def view():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    
    email = user.get('email')
    items = []
    error_message = None

    if synth_tbl:
        try:
            resp = synth_tbl.scan(FilterExpression=boto3.dynamodb.conditions.Attr('email').eq(email))
            items = sorted(resp.get('Items', []), key=lambda x: x.get('created_at', ''), reverse=True)
        except Exception as e:
            error_message = f"Error fetching data: {e}"
            
    return render_template('view.html', user=user, items=items, error_message=error_message)

# -------- Feedback --------
@application.route('/feedback', methods=['GET','POST'])
def feedback():
    user = session.get('user')
    is_guest = not user
    
    thanks = False
    error_message = None

    if request.method == 'POST':
        email = user.get('email') if user else 'guest@example.com'
        if fb_tbl:
            try:
                fb_tbl.put_item(Item={
                    'feedback': str(uuid.uuid4()),
                    'email': email,
                    'category': request.form['category'],
                    'text': request.form['feedback'],
                    'timestamp': datetime.datetime.utcnow().isoformat(),
                    'is_guest': is_guest
                })
                thanks = True
            except Exception as e:
                error_message = f"Error storing feedback: {e}"
        else:
            error_message = "Feedback system is currently unavailable."

    return render_template('feedback.html', user=user, is_guest=is_guest, thanks=thanks, error_message=error_message)

# -------- Download CSV --------
@application.route('/download/<rid>')
def download(rid):
    if not synth_tbl:
        return 'Download service unavailable', 503
    try:
        item = synth_tbl.get_item(Key={'SynteticData': rid}).get('Item')
        if not item or 'sample' not in item:
            return 'File not found', 404
        
        buf = BytesIO(item['sample'].encode('utf-8'))
        return send_file(buf, mimetype='text/csv', download_name=f'sample_{rid}.csv', as_attachment=True)
    except Exception as e:
        return 'Error downloading file', 500

# ====================
# Run App
# ====================
if __name__ == '__main__':
    if not all([dynamo, synth_tbl, fb_tbl]):
        print("Could not start application due to DynamoDB connection failure.")
    else:
        application.run(debug=True, port=5001)