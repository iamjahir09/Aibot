from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import requests
import os
import json
from dotenv import load_dotenv
import re
from django.shortcuts import render
import sqlite3

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
You are Unani-doctor, a specialized assistant in Unani medicine. Follow these strict rules EXACTLY:

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
     
User:
"""

def home(request):
    return render(request, 'index.html')

@csrf_exempt
def chat(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
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

            msg = user_message.lower().strip()
            if msg in greetings_responses:
                return JsonResponse({"response": greetings_responses[msg]})

            identity_patterns = [
                r"who are you",
                r"what are you", 
                r"what is your name", 
                r"introduce yourself"
            ]
            if any(re.search(pattern, msg) for pattern in identity_patterns):
                return JsonResponse({"response": "I am Unani-doctor, a specialized assistant in Unani and traditional Tibb medicine."})

            # Check if disease response is already cached
            conn = sqlite3.connect('user_details.db')
            cursor = conn.cursor()

            disease_query = msg  # disease name assumption from input
            cursor.execute("SELECT response FROM unani_responses WHERE disease = ?", (disease_query,))
            cached = cursor.fetchone()
            if cached:
                conn.close()
                return JsonResponse({"response": cached[0]})

            # Prepare prompt
            enhanced_message = Unani_doctor_INSTRUCTION + user_message
            ollama_payload = {
                "model": model,
                "prompt": enhanced_message,
                "stream": False
            }

            # Call model
            response = requests.post(f"{OLLAMA_API_URL}/api/generate", json=ollama_payload)
            if response.status_code == 200:
                result = response.json()
                model_response = result.get("response", "No response from model")

                # Store response if it contains standard format
                if model_response and "I hope you find the cure" in model_response:
                    try:
                        cursor.execute("INSERT OR IGNORE INTO unani_responses (disease, response) VALUES (?, ?)",
                                       (disease_query, model_response))
                        conn.commit()
                    except Exception as err:
                        print("Caching failed:", err)

                conn.close()
                return JsonResponse({"response": model_response})
            else:
                conn.close()
                return JsonResponse({"error": f"Ollama API error: {response.status_code}"}, status=500)

        except Exception as e:
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

