from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import requests
import os
import json
from dotenv import load_dotenv
import re
from django.shortcuts import render
import sqlite3
from datetime import datetime

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


Unani_doctor_INSTRUCTION = """
You are Unani-doctor, a specialized assistant in Unani medicine. Respond to each query within **1 minute**.

1. FIRST, validate if the user query contains a real and globally recognized disease name.
   - If the disease does NOT exist or is misspelled, REPLY: "Sorry, this disease does not exist. Please recheck the name."

2. If the disease exists, follow this exact structure:
   - Start with: "Addressing [Condition] with Unani"
   - Provide a BRIEF explanation of the disease based on Unani humoral theory (balgham, dam, safra, sauda).
   - DO NOT explain unrelated diseases or give general health tips.

3. After explanation, present a CLEAR TABLE with the following columns:
   Ingredient | Benefits | Usage | Precautions

4. In the table:
   - Each ingredient must be a verified Unani remedy relevant to the condition.
   - Include the **common name** of the ingredient in brackets like this: Haritaki (Terminalia chebula)
   - All benefits must be medically and traditionally accurate.
   - Dosage and precautions should be realistic and medically safe.
   - DO NOT mix botanical names (e.g., Haritaki ≠ Belleric Myrobalan)

5. List only 4–5 ingredients MAXIMUM.
6. DO NOT use mixed, incorrect, or non-existent ingredient mappings.
7. DO NOT hallucinate information. If unsure, say "Research ongoing".

8. Finish with the exact sentence: "I hope you find the cure, Takecare"

9. DO NOT answer anything unrelated to diseases or Unani treatment.
   - If the user asks something off-topic (e.g., politics, tech, jokes), reply: 
     "I'm your Unani health assistant. I can only help with Unani-based health queries."

Note: Answer should be provided **within 1 minute**.
User:
"""


def index(request):
    return render(request, 'index.html')

def home(request):
    return render(request, 'home.html')

def logout(request):
    return render(request,'home.html')

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

            # Check if user exists with matching email and password
            cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password))
            user = cursor.fetchone()
            conn.close()

            if user:
                request.session['user_id'] = user[0]
                return redirect('index')  # 'index' must be the name of your URL pattern for index.html
            else:
                return render(request, 'login.html', {'error': 'Invalid email or password.'})

        except Exception as e:
            return render(request, 'login.html', {'error': f'Error: {str(e)}'})

    return render(request, 'login.html')

import sqlite3
import re
import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

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
                return JsonResponse({"response": greetings_responses[user_message]})

            # Identity questions
            identity_patterns = [
                r"who are you",
                r"what are you", 
                r"what is your name", 
                r"introduce yourself"
            ]
            if any(re.search(pattern, user_message) for pattern in identity_patterns):
                return JsonResponse({"response": "I am Unani-doctor, a specialized assistant in Unani and traditional Tibb medicine."})

            # Step 1: Match user message with known diseases
            conn = sqlite3.connect("user_details.db")
            cursor = conn.cursor()
            cursor.execute("SELECT disease, response FROM unani_responses")
            rows = cursor.fetchall()

            matched_response = None
            for disease, response in rows:
                if disease.lower() in user_message:
                    matched_response = response
                    break

            if matched_response:
                conn.close()
                return JsonResponse({"response": matched_response})

            # Step 2: No match found, call Ollama model
            enhanced_message = Unani_doctor_INSTRUCTION + user_message
            ollama_payload = {
                "model": model,
                "prompt": enhanced_message,
                "stream": False
            }

            response = requests.post(f"{OLLAMA_API_URL}/api/generate", json=ollama_payload)

            if response.status_code == 200:
                result = response.json()
                model_response = result.get("response", "No response from model")

                # Try to extract a disease name from prompt (fallback to full prompt)
                extracted_disease = user_message.split()[0:5]
                possible_disease = " ".join(extracted_disease)

                # Store model response in database
                try:
                    cursor.execute("INSERT INTO unani_responses (disease, response) VALUES (?, ?)",
                                   (possible_disease, model_response))
                    conn.commit()
                except Exception as err:
                    print("Error while caching model response:", err)

                conn.close()
                return JsonResponse({"response": model_response})
            else:
                conn.close()
                return JsonResponse({"error": f"Ollama API error: {response.status_code}"}, status=500)

        except Exception as e:
            print(f"Error in chat endpoint: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)

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

# views.py
from django.http import JsonResponse

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
