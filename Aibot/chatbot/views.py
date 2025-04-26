from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
import os
import json
from dotenv import load_dotenv
import re
from django.shortcuts import render
import sqlite3
from datetime import datetime
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import logout
from django.shortcuts import redirect



# Load environment variables
load_dotenv()

OLLAMA_API_URL = os.getenv('OLLAMA_API_URL', 'http://localhost:11434')
DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', 'unani-doctor')

def create_database():
    """
    SQLite database aur tables create karta hai (if not exists).
    """
    conn = sqlite3.connect('user_details.db')
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON;')

    # Users table
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Conversations table
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            response TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Medicine Reminders table
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS medicine_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            medicine_name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            schedule TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Unani Ingredients table
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS unani_ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingredient_name TEXT NOT NULL,
            benefits TEXT NOT NULL,
            usage TEXT NOT NULL,
            diseases TEXT NOT NULL  
        )
    ''')

    # Unani response cache table
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS unani_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            disease TEXT UNIQUE NOT NULL,
            response TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print("Database and tables created successfully!")

create_database()

@csrf_exempt
def chat(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').lower().strip()
            model = data.get('model', DEFAULT_MODEL)

            # Greeting responses
            greetings_responses = {
                "hi": "Hi there! How can I assist you today?",
                "hello": "Hello! How can I help you?",
                "hey": "Hey! What can I do for you?",
                "greetings": "Greetings! What brings you here today?",
                "good morning": "Good morning! Hope you're feeling well.",
                "good afternoon": "Good afternoon! How can I help you?",
                "good evening": "Good evening! What can I do for you?",
                "salam": "Wa alaikum assalam! How may I assist you today?",
                "assalamualaikum": "Wa alaikum assalam! How may I help you?",
                "assalamu alaikum": "Wa alaikum assalam! How can I assist you today?"
            }

            if user_message in greetings_responses:
                bot_response = greetings_responses[user_message]
                store_conversation(request, user_message, bot_response)
                return JsonResponse({"response": bot_response})

            # Identity questions
            identity_patterns = [
                r"who are you",
                r"what are you", 
                r"what is your name", 
                r"introduce yourself"
            ]
            if any(re.search(pattern, user_message) for pattern in identity_patterns):
                bot_response = "I am Unani-doctor, a specialized assistant in Unani and traditional Tibb medicine."
                store_conversation(request, user_message, bot_response)
                return JsonResponse({"response": bot_response})

            # Initialize response variable
            bot_response = None

            # Function to extract disease name from user message
            def extract_disease(message):
                disease_patterns = [
                    r'(?:i\s*(?:have|am\s*having|ve\s*got)|suffering\s*from|diagnosed\s*with|affected\s*by)\s+([a-z\s]+?)(?:\s*(?:for|since|from|please|now|that|which|\?|\.|$))',
                    r'(?:treatment|remedy|cure|solution|help)\s+(?:for|with)\s+([a-z\s]+?)(?:\s*(?:please|\?|\.|$))',
                    r'my\s+([a-z\s]+?)(?:\s*(?:is|has|become|feels|\?|\.|$))',
                    r'(?:about|information\s*on|details\s*of)\s+([a-z\s]+?)(?:\s*(?:disease|problem|\?|\.|$))',
                    r'\b(?:having|got)\s+([a-z\s]+?)(?:\s*(?:problem|issue|pain|\?|\.|$))'
                ]
                
                for pattern in disease_patterns:
                    match = re.search(pattern, message, re.IGNORECASE)
                    if match:
                        disease = match.group(1).strip()
                        disease = re.sub(r'\b(?:please|plz|help|me|my|give|provide|suggest|recommend|tell|about|information|on|for|with|treatment|remedy|cure|solution|disease|problem|issue|pain)\b', '', disease, flags=re.IGNORECASE).strip()
                        if disease:
                            return disease

                # Added EXTRA smart extraction for very long messages
                sentences = re.split(r'[.?!]', message)
                for sentence in sentences:
                    for pattern in disease_patterns:
                        match = re.search(pattern, sentence, re.IGNORECASE)
                        if match:
                            disease = match.group(1).strip()
                            disease = re.sub(r'\b(?:please|plz|help|me|my|give|provide|suggest|recommend|tell|about|information|on|for|with|treatment|remedy|cure|solution|disease|problem|issue|pain)\b', '', disease, flags=re.IGNORECASE).strip()
                            if disease:
                                return disease

                if len(message.split()) <= 4 and not any(word in message for word in ['you', 'your', 'who', 'what']):
                    return message
                
                return None

            # Extract disease name from user message
            disease_name = extract_disease(user_message)

            # Step 1: Match user message with known diseases dynamically
            conn = sqlite3.connect("user_details.db")
            cursor = conn.cursor()

            if disease_name:
                cursor.execute("SELECT response FROM unani_responses WHERE disease LIKE ?", (f"%{disease_name}%",))
                row = cursor.fetchone()

                if row:
                    bot_response = row[0]
                    store_conversation(request, user_message, bot_response)
                    conn.close()
                    return JsonResponse({"response": bot_response})

                cursor.execute("SELECT disease, response FROM unani_responses")
                rows = cursor.fetchall()

                matched_response = None
                for db_disease, response in rows:
                    pattern = r'\b' + re.escape(db_disease.lower()) + r'\b'
                    if re.search(pattern, disease_name):
                        matched_response = response
                        break

                if matched_response:
                    bot_response = matched_response
                    store_conversation(request, user_message, bot_response)
                    conn.close()
                    return JsonResponse({"response": bot_response})

            # Step 2: No match found, call Ollama model
            enhanced_message = Unani_doctor_INSTRUCTION + (disease_name if disease_name else user_message)
            ollama_payload = {
                "model": model,
                "prompt": enhanced_message,
                "stream": False
            }

            api_response = requests.post(f"{OLLAMA_API_URL}/api/generate", json=ollama_payload)

            if api_response.status_code == 200:
                result = api_response.json()
                bot_response = result.get("response", "No response from model")

                store_conversation(request, user_message, bot_response)

                if disease_name and bot_response:
                    try:
                        cursor.execute("""
                            INSERT OR REPLACE INTO unani_responses (disease, response) 
                            VALUES (?, ?)
                        """, (disease_name, bot_response))
                        conn.commit()
                    except Exception as e:
                        print(f"Error caching disease response: {e}")

                conn.close()
                return JsonResponse({"response": bot_response})

            else:
                conn.close()
                return JsonResponse({"error": f"Ollama API error: {api_response.status_code}"}, status=500)

        except Exception as e:
            print(f"Error in chat endpoint: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)

def get_user_id_from_email(email):
    """
    Fetch user_id from the users table using the email.
    """
    conn = sqlite3.connect('user_details.db')
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    result = cursor.fetchone()

    conn.close()

    if result:
        return result[0]  # Return user ID
    else:
        raise ValueError("User not found")

def store_conversation(request, user_message, bot_response):
    try:
        email = request.session.get('email')
        if not email:
            print("Warning: User email not found in session")
            return False
        
        # Fetch user ID using email
        user_id = get_user_id_from_email(email)
        if not user_id:
            print(f"Warning: No user found with email: {email}")
            return False
        
        conn = None
        try:
            conn = sqlite3.connect('user_details.db')
            cursor = conn.cursor()
            
            # Enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = ON")
            
            # Insert conversation
            cursor.execute(""" 
                INSERT INTO conversations (user_id, message, response, timestamp)
                VALUES (?, ?, ?, ?)
            """, (user_id, user_message, bot_response, datetime.now()))
            
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Database error in store_conversation: {str(e)}")
            return False
            
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        print(f"General error in store_conversation: {str(e)}")
        return False


@csrf_exempt
def get_chat_history(request):
    if request.method == 'GET':
        try:
            user_id = request.session.get('user_id')
            if not user_id:
                return JsonResponse({'error': 'User not authenticated'}, status=401)
            
            conn = sqlite3.connect('user_details.db')
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT message, response, timestamp 
                FROM conversations 
                WHERE user_id = ? 
                ORDER BY timestamp DESC
                LIMIT 50
            """, (user_id,))
            
            def format_response(response):
                # Check if response contains a table pattern
                if "| Ingredient | Benefits | Usage | Precautions |" in response:
                    # Extract the table part
                    table_start = response.find("| Ingredient | Benefits | Usage | Precautions |")
                    table_end = response.find("\n\n", table_start)
                    table_content = response[table_start:table_end]
                    
                    # Convert markdown table to HTML table with CSS
                    table_html = """
                    <div class="unani-table-container">
                        <table class="unani-table">
                            <thead>
                                <tr>
                                    <th>Ingredient</th>
                                    <th>Benefits</th>
                                    <th>Usage</th>
                                    <th>Precautions</th>
                                </tr>
                            </thead>
                            <tbody>
                    """
                    
                    # Process table rows
                    rows = [row.strip() for row in table_content.split('\n') if row.strip()]
                    for row in rows[2:]:  # Skip header and separator lines
                        if row.startswith('|'):
                            cells = [cell.strip() for cell in row.split('|')[1:-1]]
                            if len(cells) == 4:
                                table_html += f"""
                                <tr>
                                    <td>{cells[0]}</td>
                                    <td>{cells[1]}</td>
                                    <td>{cells[2]}</td>
                                    <td>{cells[3]}</td>
                                </tr>
                                """
                    
                    table_html += """
                            </tbody>
                        </table>
                    </div>
                    """
                    
                    # Replace markdown table with HTML table in response
                    return response[:table_start] + table_html + response[table_end:]
                return response
            
            history = [{
                'message': row[0],
                'response': format_response(row[1]),
                'timestamp': row[2]
            } for row in cursor.fetchall()]
            
            conn.close()
            return JsonResponse({'history': history})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

Unani_doctor_INSTRUCTION = """
You are Unani-doctor, a specialized assistant in Unani medicine. Respond to each query within **1 minute**.

1. LANGUAGE HANDLING:
   - Automatically detect and respond in the user's language
   - Maintain all Unani medical terminology accurately
   - For non-English queries, include botanical names in parentheses

2. FIRST, validate if the user query contains a real and globally recognized disease name.
   - If the disease does NOT exist or is misspelled, REPLY: "Sorry, this disease does not exist. Please recheck the name."

3. If the query is about a specific Unani ingredient (e.g., saffron, haritaki):
   - DO NOT provide a table.
   - Respond with exactly 7 bullet points.
   - Each point should be MAX 2 lines.
   - Include known Unani benefits, traditional uses, and medicinal effects.
   - Avoid false claims or unverified data.

4. If the disease exists, follow this exact structure:
   - Start with: "Addressing [Condition] with Unani"
   - Provide a BRIEF explanation of the disease based on Unani humoral theory (balgham, dam, safra, sauda).
   - DO NOT explain unrelated diseases or give general health tips.

5. After explanation, present a CLEAR TABLE with the following columns:
   Ingredient | Benefits | Usage | Precautions

6. In the table:
   - Each ingredient must be a verified Unani remedy relevant to the condition.
   - Include the **common name** of the ingredient in brackets like this: Haritaki (Terminalia chebula)
   - All benefits must be medically and traditionally accurate.
   - Dosage and precautions should be realistic and medically safe.
   - DO NOT mix botanical names (e.g., Haritaki ≠ Belleric Myrobalan)

7. List only 4–5 ingredients MAXIMUM.
8. DO NOT use mixed, incorrect, or non-existent ingredient mappings.
9. DO NOT hallucinate information. If unsure, say "Research ongoing".

10. Finish with the exact sentence: "I hope you find the cure. Take care! "

11. DO NOT answer anything unrelated to diseases or Unani treatment.
   - If the user asks something off-topic (e.g., politics, tech, jokes), reply: 
     "I'm your Unani health assistant. I can only help with Unani-based health queries."

12. User Language Detection:
    -Respond in the language that the user is using, whether it's Hindi, Marathi, Urdu, Hinglish, Turkish, or any other global language.
    -The response will match the language of the user's sentence, regardless of the script used (e.g., Marathi, Hindi, Urdu, Hinglish).

13. Ingredient Information:
    -If the user asks for details about any ingredient, provide information in bullet points.
    -Limit to 6 points maximum.
    -Each point should be short (max 2 lines per point).

Note: Answer should be provided **within 1 minute**.
User:
"""


def index(request):
    return render(request, 'index.html')

def home(request):
    return render(request, 'home.html')



def logout_view(request):
    try:
        del request.session['user_id']  # session clear karo
    except KeyError:
        pass
    return redirect('home')  # ya login page




def check_session(request):
    if 'user_id' in request.session:
        return JsonResponse({'logged_in': True})
    else:
        return JsonResponse({'logged_in': False})



@csrf_exempt
def signup(request):
    if request.method == 'POST':
        try:
            email = request.POST.get('email')
            password = request.POST.get('password')

            if not email or not password:
                return render(request, 'signup.html', {'error': 'Email and password are required.'})

            conn = sqlite3.connect('user_details.db')
            cursor = conn.cursor()

            # Check if user already exists
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                conn.close()
                return render(request, 'signup.html', {'error': 'User already exists.'})

            # Insert new user
            cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
            conn.commit()
            conn.close()

            return render(request, 'login.html', {'message': 'Signup successful! Please login.'})

        except Exception as e:
            return render(request, 'signup.html', {'error': f'Error: {str(e)}'})

    return render(request, 'signup.html')


from django.shortcuts import redirect

@csrf_exempt
def login(request):
    if request.method == 'POST':
        try:
            email = request.POST.get('email')
            password = request.POST.get('password')

            conn = sqlite3.connect('user_details.db')
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM users WHERE email = ? AND password = ?", (email, password))
            user = cursor.fetchone()
            conn.close()

            if user:
                request.session['user_id'] = user[0]
                request.session['email'] = email

                request.session.set_expiry(60 * 60 * 24 * 365)  # 1 saal tak login
                return redirect('index')
            else:
                return render(request, 'login.html', {'error': 'Invalid email or password.'})

        except Exception as e:
            return render(request, 'login.html', {'error': f'Error: {str(e)}'})

    return render(request, 'login.html')



# Helper function to check if the disease exists in the database and return its ingredients
def get_disease_ingredients(disease):
    """
    Returns the ingredients associated with a given disease if it exists in the database.
    """
    try:
        conn = sqlite3.connect('user_details.db')
        cursor = conn.cursor()

        # Query to find the disease and associated ingredients
        cursor.execute("SELECT response FROM unani_responses WHERE disease LIKE ?", ('%' + disease + '%',))
        result = cursor.fetchone()

        conn.close()

        if result:
            return result[0]  # Returning ingredients list as a string or JSON
        else:
            return None  # No match found
    except Exception as e:
        print(f"Error in get_disease_ingredients: {str(e)}")
        return None


@csrf_exempt
def get_conversation_history(user_id):
    """
    Fetches conversation history for a specific user.
    """
    conn = sqlite3.connect('user_details.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT message, response, timestamp
        FROM conversations
        WHERE user_id = ?
        ORDER BY timestamp ASC
    ''', (user_id,))
    history = cursor.fetchall()
    conn.close()
    return history


@csrf_exempt
def get_models(request):
    if request.method == 'GET':
        try:
            response = requests.get(f"{OLLAMA_API_URL}/api/tags")
            if response.status_code == 200:
                return JsonResponse(response.json())
            else:
                return JsonResponse({"error": f"Ollama API error: {response.status_code}"}, status=500)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=405)


def get_conversation_history(user_id):
    """
    Fetches conversation history for a specific user.
    """
    conn = sqlite3.connect('user_details.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT message, response, timestamp
        FROM conversations
        WHERE user_id = ?
        ORDER BY timestamp ASC
    ''', (user_id,))
    history = cursor.fetchall()
    conn.close()
    return history

@csrf_exempt
def chatbot_response(request):
    """
    Handles chatbot responses via AJAX and stores conversations.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get("message", "")
            user_id = request.session.get("user_id")  # Get the user ID from session

            if not user_id:
                return JsonResponse({"error": "User not authenticated"}, status=401)

            if not user_message:
                return JsonResponse({"error": "No message provided"}, status=400)

            # Reuse the chat logic
            chat_request = {
                "body": json.dumps({"message": user_message}),
                "method": "POST"
            }

            # Mock the request object for `chat()` view
            class DummyRequest:
                def __init__(self, body):
                    self.body = body
                    self.method = "POST"

            dummy_request = DummyRequest(json.dumps({"message": user_message}))
            response_json = chat(dummy_request).content
            response_data = json.loads(response_json)

            if "response" in response_data:
                model_response = response_data["response"]

                # Save the chat to the database
                conn = sqlite3.connect('user_details.db')
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO conversations (user_id, message, response)
                    VALUES (?, ?, ?)
                ''', (user_id, user_message, model_response))
                conn.commit()
                conn.close()

                return JsonResponse({"response": model_response})
            else:
                return JsonResponse({"error": response_data.get("error", "Unknown error")}, status=500)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)




def check_login_status(request):
    return JsonResponse({'is_authenticated': request.user.is_authenticated})


def is_valid_disease(disease_name):
    """
    Checks if the disease exists in the Unani database.
    """
    conn = sqlite3.connect('user_details.db')
    cursor = conn.cursor()

    # Query to find if the disease exists
    cursor.execute("SELECT * FROM unani_ingredients WHERE diseases LIKE ?", ('%' + disease_name + '%',))
    disease = cursor.fetchone()

    conn.close()
    
    return disease is not None

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .voice_utils import UnaniVoiceAssistant
import io
import json

@csrf_exempt
def voice_to_text(request):
    """API endpoint to convert voice to text"""
    if request.method == 'POST':
        try:
            # Check if audio file was uploaded
            if 'audio' not in request.FILES:
                return JsonResponse({
                    'error': 'No audio file provided',
                    'status': 'error'
                }, status=400)
            
            # Create in-memory file-like object
            audio_data = io.BytesIO()
            
            # Stream uploaded file directly to memory
            for chunk in request.FILES['audio'].chunks():
                audio_data.write(chunk)
            audio_data.seek(0)  # Rewind to start of stream
            
            # Process audio
            assistant = UnaniVoiceAssistant()
            recognized_text = assistant.process_audio(audio_data)
            
            if recognized_text:
                return JsonResponse({
                    'text': recognized_text, 
                    'status': 'success',
                    'language': 'hi-IN'
                })
            
            return JsonResponse({
                'error': 'Could not understand audio', 
                'status': 'error'
            }, status=400)
            
        except Exception as e:
            return JsonResponse({
                'error': str(e),
                'status': 'error'
            }, status=500)
    
    return JsonResponse({
        'error': 'Invalid request method', 
        'status': 'error'
    }, status=405)
from django.conf import settings
from .models import ChatMessage, UploadedFile
@csrf_exempt
def handle_file_upload(request):
    if request.method == 'POST':
        try:
            # Ensure upload directory exists
            os.makedirs(os.path.join(settings.MEDIA_ROOT, 'uploads'), exist_ok=True)
            
            if not request.FILES:
                return JsonResponse({'status': 'error', 'message': 'No files provided'}, status=400)

            files = request.FILES.getlist('files')
            message_text = request.POST.get('message', '')
            chat = None

            # Handle message saving
            if message_text:
                try:
                    email = request.session.get('email')
                    if email:
                        user_id = get_user_id_from_email(email)  # Ensure this function exists
                        chat = ChatMessage.objects.create(
                            user_id=user_id,
                            message=message_text
                        )
                except Exception as e:
                    print(f"Message save error: {str(e)}")

            # Process files
            saved_files = []
            for file in files:
                try:
                    uploaded = UploadedFile.objects.create(
                        file=file,
                        message=chat
                    )
                    saved_files.append({
                        'name': file.name,
                        'url': uploaded.file.url,
                        'size': file.size
                    })
                except Exception as e:
                    print(f"File save error for {file.name}: {str(e)}")
                    continue

            return JsonResponse({
                'status': 'success',
                'files': saved_files,
                'message': message_text,
                'message_id': chat.id if chat else None
            })

        except Exception as e:
            import traceback
            traceback.print_exc()  # Log full error to console
            return JsonResponse({
                'status': 'error',
                'message': f"Server error: {str(e)}"
            }, status=500)

    return JsonResponse({
        'status': 'error',
        'message': 'Only POST requests allowed'
    }, status=405)
@csrf_exempt
def text_to_speech(request):
    """API endpoint to convert text to speech"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            text = data.get('text', '')
            
            if not text:
                return JsonResponse({
                    'error': 'No text provided',
                    'status': 'error'
                }, status=400)
            
            assistant = UnaniVoiceAssistant()
            assistant.speak(text)
            
            return JsonResponse({
                'status': 'success',
                'message': 'Text spoken successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'error': str(e),
                'status': 'error'
            }, status=500)
    
    return JsonResponse({
        'error': 'Invalid request method', 
        'status': 'error'
    }, status=405)