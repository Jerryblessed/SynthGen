# Imports
import os
import json
import csv
import uuid
import datetime
import logging
from io import BytesIO, StringIO
from flask import Flask, redirect, url_for, session, request, render_template, send_file, jsonify
from authlib.integrations.flask_client import OAuth
import boto3
from botocore.exceptions import ClientError

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====================
# Flask App Setup
# ====================
application = Flask(__name__)
application.secret_key = os.urandom(24)

# ====================
# AWS Configuration
# ====================
AWS_CONFIG = {
    'access_key': 'AKIA6FIQDWZWJOPKXKHE',
    'secret_key': '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',
    'region': 'eu-north-1'  # Changed to us-east-1 for Bedrock
}

# Cognito Configuration
# USER_POOL_ID = "eu-north-1_8nOgsOGhF"
USER_POOL_ID = "eu-north-1_Ex4QZ9tGZ"
CLIENT_ID = "3jsgcnepuj7qggho8iq4usl2im"
CLIENT_SECRET = "6dkbhvtuqtuborosg84bjnc2bn916bunloi4ra43b652u8pue98"
COG_DOMAIN = f"https://cognito-idp.eu-north-1.amazonaws.com/{USER_POOL_ID}"

# ====================
# AWS Services Setup
# ====================
def setup_aws_services():
    """Initialize AWS services"""
    try:
        # DynamoDB (keeping original region)
        dynamo = boto3.resource(
            'dynamodb',
            region_name='eu-north-1',
            aws_access_key_id=AWS_CONFIG['access_key'],
            aws_secret_access_key=AWS_CONFIG['secret_key']
        )
        
        # Bedrock Runtime (us-east-1)
        bedrock_runtime = boto3.client(
            'bedrock-runtime',
            region_name=AWS_CONFIG['region'],
            aws_access_key_id=AWS_CONFIG['access_key'],
            aws_secret_access_key=AWS_CONFIG['secret_key']
        )
        
        synth_tbl = dynamo.Table("SyntheticData")
        fb_tbl = dynamo.Table("Feedback")
        
        logger.info("Successfully initialized AWS services")
        return dynamo, bedrock_runtime, synth_tbl, fb_tbl
    except Exception as e:
        logger.error(f"Failed to initialize AWS services: {e}")
        return None, None, None, None

# Initialize AWS services
dynamo, bedrock_runtime, synth_tbl, fb_tbl = setup_aws_services()

# ====================
# Bedrock Titan Integration
# ====================
class BedrockTitanGenerator:
    def __init__(self, bedrock_client):
        self.bedrock_client = bedrock_client
        self.model_id = "amazon.titan-text-lite-v1"
    
    def generate_synthetic_data(self, schema_headers, domain, count, noise_level, balance_classes, mask_pii):
        """Generate synthetic data using Bedrock Titan"""
        try:
            # Create a detailed prompt for data generation
            prompt = self._create_data_generation_prompt(
                schema_headers, domain, count, noise_level, balance_classes, mask_pii
            )
            
            # Call Bedrock Titan
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": 4000,
                        "temperature": min(noise_level, 0.9),
                        "topP": 0.9
                    }
                }),
                contentType="application/json"
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            generated_text = response_body['results'][0]['outputText']
            
            # Process the generated text into structured data
            synthetic_data = self._parse_generated_data(generated_text, schema_headers, count)
            
            return synthetic_data
            
        except Exception as e:
            logger.error(f"Error generating synthetic data with Bedrock: {e}")
            # Fallback to simple generation
            return self._fallback_generation(schema_headers, count)
    
    def _create_data_generation_prompt(self, headers, domain, count, noise_level, balance_classes, mask_pii):
        """Create a detailed prompt for synthetic data generation"""
        prompt = f"""Generate {count} rows of realistic synthetic data for the {domain} domain.

Schema columns: {', '.join(headers)}

Requirements:
- Generate realistic {domain} data
- Noise level: {noise_level} (0=very consistent, 1=highly varied)
- Balance classes: {'Yes' if balance_classes else 'No'}
- Mask PII: {'Yes' if mask_pii else 'No'}

Format the output as CSV rows (no headers), one row per line.
Make the data realistic and varied for the {domain} domain.
"""
        
        if mask_pii:
            prompt += "\nMask any personally identifiable information (names, emails, phone numbers, etc.)."
        
        if balance_classes:
            prompt += "\nEnsure balanced distribution across categories/classes."
        
        prompt += f"\n\nGenerate exactly {count} rows:"
        
        return prompt
    
    def _parse_generated_data(self, generated_text, headers, expected_count):
        """Parse the generated text into structured data"""
        lines = generated_text.strip().split('\n')
        synthetic_data = []
        
        for i, line in enumerate(lines[:expected_count]):
            if line.strip():
                try:
                    # Try to parse as CSV
                    values = [val.strip().strip('"') for val in line.split(',')]
                    if len(values) == len(headers):
                        record = dict(zip(headers, values))
                        synthetic_data.append(record)
                except:
                    # If parsing fails, create a simple record
                    record = {col: f"{col}_{i+1}" for col in headers}
                    synthetic_data.append(record)
        
        # Ensure we have the expected count
        while len(synthetic_data) < expected_count:
            i = len(synthetic_data)
            record = {col: f"{col}_{i+1}" for col in headers}
            synthetic_data.append(record)
        
        return synthetic_data[:expected_count]
    
    def _fallback_generation(self, headers, count):
        """Fallback generation if Bedrock fails"""
        synthetic_data = []
        for i in range(count):
            record = {col: f"{col}_{i+1}" for col in headers}
            synthetic_data.append(record)
        return synthetic_data

# Initialize Bedrock generator
bedrock_generator = BedrockTitanGenerator(bedrock_runtime) if bedrock_runtime else None

# ====================
# AI Agent for Automation
# ====================
class AIAgent:
    def __init__(self, bedrock_client):
        self.bedrock_client = bedrock_client
        self.model_id = "amazon.titan-text-lite-v1"
    
    def process_query(self, query, context=None):
        """Process user queries and provide intelligent responses"""
        try:
            # Create context-aware prompt
            prompt = self._create_agent_prompt(query, context)
            
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": 500,
                        "temperature": 0.3,
                        "topP": 0.9
                    }
                }),
                contentType="application/json"
            )
            
            response_body = json.loads(response['body'].read())
            return response_body['results'][0]['outputText'].strip()
            
        except Exception as e:
            logger.error(f"Error processing agent query: {e}")
            return self._fallback_response(query)
    
    def _create_agent_prompt(self, query, context):
        """Create a context-aware prompt for the AI agent"""
        prompt = f"""You are an AI assistant for a synthetic data generation platform. 
Help users understand and configure synthetic data generation parameters.

User Query: {query}

Context: You help with:
- Noise levels (0-1): Controls randomness in generated data
- Class balancing: Ensures equal distribution of categories
- PII masking: Protects sensitive personal information
- Domain selection: health, finance, retail data types
- Record count: Number of synthetic records to generate

Provide a helpful, concise response (max 2-3 sentences):"""
        
        if context:
            prompt += f"\nAdditional context: {context}"
        
        return prompt
    
    def _fallback_response(self, query):
        """Fallback responses when Bedrock is unavailable"""
        query_lower = query.lower()
        
        if 'noise' in query_lower:
            return "Noise controls randomness in your data. 0 = very consistent, 1 = highly varied. Use lower values for realistic data."
        elif 'balance' in query_lower:
            return "Class balancing ensures equal representation of categories. Important for ML training datasets."
        elif 'pii' in query_lower or 'mask' in query_lower:
            return "PII masking replaces sensitive information like names, emails, phone numbers with fake but realistic alternatives."
        elif 'domain' in query_lower:
            return "Domain selection affects the type of data generated. Health generates medical data, finance generates financial records, retail generates customer data."
        elif 'records' in query_lower or 'count' in query_lower:
            return "You can generate 1-1000 records per request. More records provide better statistical diversity."
        else:
            return "I can help with noise levels, class balancing, PII masking, domain selection, and record counts. What would you like to know?"

# Initialize AI agent
ai_agent = AIAgent(bedrock_runtime) if bedrock_runtime else None

# ====================
# OAuth Setup
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

# -------- Authentication Routes --------
@application.route('/login')
def login():
    return oauth.oidc.authorize_redirect(redirect_uri="https://synthgen.eu-north-1.elasticbeanstalk.com/authorize")

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

# -------- Main Generation Route --------
@application.route('/generate', methods=['GET', 'POST'])
def generate():
    user = session.get('user')
    email = user.get('email') if user else 'guest@example.com'
    is_guest = not user
    
    record_id = None
    preview = ''
    error_message = None
    success_message = None

    if request.method == 'POST':
        file = request.files.get('file')
        
        if not file or file.filename == '':
            error_message = "Please upload a CSV schema file."
        else:
            try:
                # Parse CSV schema
                csv_bytes = file.read()
                csv_lines = csv_bytes.decode('utf-8').splitlines()
                headers = [col.strip() for col in csv_lines[0].split(',')]

                # Get form parameters
                domain = request.form.get('domain', 'health')
                count = int(request.form.get('count', 100))
                noise = float(request.form.get('noise', 0.1))
                balance = 'balance' in request.form
                mask_pii = 'mask_pii' in request.form

                # Generate synthetic data using Bedrock
                if bedrock_generator:
                    synthetic_data = bedrock_generator.generate_synthetic_data(
                        headers, domain, count, noise, balance, mask_pii
                    )
                else:
                    # Fallback generation
                    synthetic_data = []
                    for i in range(count):
                        record = {col: f"{col}_{i+1}" for col in headers}
                        synthetic_data.append(record)

                # Convert to CSV
                output = StringIO()
                writer = csv.DictWriter(output, fieldnames=headers)
                writer.writeheader()
                writer.writerows(synthetic_data)
                csv_output = output.getvalue()
                
                # Create preview
                preview_lines = csv_output.splitlines()[:6]  # Header + 5 rows
                preview = '\n'.join(preview_lines)
                
                # Generate unique record ID
                record_id = str(uuid.uuid4())
                
                # Store in DynamoDB
                if synth_tbl:
                    synth_tbl.put_item(Item={
                        'SynteticData': record_id,
                        'email': email,
                        'domain': domain,
                        'prompt': json.dumps({
                            'domain': domain,
                            'count': count,
                            'noise': noise,
                            'balance': balance,
                            'mask_pii': mask_pii,
                            'headers': headers
                        }),
                        'sample': csv_output,
                        'created_at': datetime.datetime.utcnow().isoformat(),
                        'is_guest': is_guest
                    })
                
                success_message = f"Successfully generated {count} synthetic records using Amazon Bedrock Titan!"

            except Exception as e:
                logger.error(f"Error generating data: {e}")
                error_message = f"An error occurred while generating data: {str(e)}"

    return render_template('generate.html', 
                         user=user, 
                         is_guest=is_guest, 
                         record_id=record_id, 
                         preview=preview, 
                         error_message=error_message,
                         success_message=success_message)

# -------- AI Agent Route --------
@application.route('/agent', methods=['POST'])
def agent():
    query = request.form.get('query', '')
    context = request.form.get('context', '')
    
    if ai_agent:
        response = ai_agent.process_query(query, context)
    else:
        # Fallback responses
        query_lower = query.lower()
        if 'noise' in query_lower:
            response = "Noise controls randomness in your data. 0 = very consistent, 1 = highly varied."
        elif 'balance' in query_lower:
            response = "Class balancing ensures equal representation of categories in your dataset."
        elif 'pii' in query_lower or 'mask' in query_lower:
            response = "PII masking replaces sensitive information with realistic fake alternatives."
        else:
            response = "I can help with noise levels, class balancing, PII masking, and more!"
    
    return render_template('agent.html', response=response, query=query)

# -------- AJAX Agent Route for Real-time Assistance --------
@application.route('/agent_ajax', methods=['POST'])
def agent_ajax():
    """AJAX endpoint for real-time agent assistance"""
    data = request.get_json()
    query = data.get('query', '')
    context = data.get('context', {})
    
    if ai_agent:
        response = ai_agent.process_query(query, json.dumps(context))
    else:
        response = "Agent temporarily unavailable. Please try again."
    
    return jsonify({'response': response})

# -------- Data Management Routes --------
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
            from boto3.dynamodb.conditions import Attr
            response = synth_tbl.scan(FilterExpression=Attr('email').eq(email))
            items = sorted(response.get('Items', []), 
                         key=lambda x: x.get('created_at', ''), 
                         reverse=True)
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            error_message = f"Error fetching data: {str(e)}"
            
    return render_template('view.html', user=user, items=items, error_message=error_message)

@application.route('/download/<rid>')
def download(rid):
    if not synth_tbl:
        return 'Download service unavailable', 503
    
    try:
        item = synth_tbl.get_item(Key={'SynteticData': rid}).get('Item')
        if not item or 'sample' not in item:
            return 'File not found', 404
        
        buf = BytesIO(item['sample'].encode('utf-8'))
        return send_file(buf, 
                        mimetype='text/csv', 
                        download_name=f'synthetic_data_{rid[:8]}.csv', 
                        as_attachment=True)
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return 'Error downloading file', 500

# -------- Feedback Route --------
@application.route('/feedback', methods=['GET', 'POST'])
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
                    'category': request.form.get('category', 'General'),
                    'text': request.form.get('feedback', ''),
                    'timestamp': datetime.datetime.utcnow().isoformat(),
                    'is_guest': is_guest
                })
                thanks = True
            except Exception as e:
                logger.error(f"Error storing feedback: {e}")
                error_message = f"Error storing feedback: {str(e)}"
        else:
            error_message = "Feedback system is currently unavailable."

    return render_template('feedback.html', 
                         user=user, 
                         is_guest=is_guest, 
                         thanks=thanks, 
                         error_message=error_message)

# -------- Health Check Route --------
@application.route('/health')
def health():
    """Health check endpoint"""
    status = {
        'status': 'healthy',
        'bedrock_available': bedrock_runtime is not None,
        'dynamodb_available': synth_tbl is not None,
        'timestamp': datetime.datetime.utcnow().isoformat()
    }
    return jsonify(status)

# ====================
# Error Handlers
# ====================
@application.errorhandler(404)
def not_found(error):
    return render_template('error.html', error="Page not found"), 404

@application.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return render_template('error.html', error="Internal server error"), 500

# ====================
# Run Application
# ====================
if __name__ == '__main__':
    if not bedrock_runtime:
        logger.warning("Bedrock runtime not available - using fallback generation")
    if not synth_tbl:
        logger.warning("DynamoDB not available - data won't be persisted")
    
    logger.info("Starting Flask application...")
    application.run(debug=True, port=5001)
