from django.http import JsonResponse
from django.shortcuts import render
import requests
import time

OLLAMA_URL = "http://localhost:11434"

def ask_unani_doctor(question):
    try:
        print(f"\n📨 Sending question to Unani-Doctor: '{question}'")
        start_time = time.time()

        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": "unani-doctor",
                "prompt": question,
                "stream": False
            },
            timeout=600
        )

        processing_time = time.time() - start_time
        print(f"⏱️ Response received in {processing_time:.2f} seconds")

        if response.status_code == 200:
            response_data = response.json()
            return response_data.get("response", "⚠️ No response key found in JSON")
        else:
            return f"⚠️ API returned status {response.status_code}"

    except requests.exceptions.ConnectionError:
        return "❌ Ollama server not running. Please start it with 'ollama serve'"
    except requests.exceptions.Timeout:
        return "⚠️ Request timeout. Try a simpler query."
    except Exception as e:
        return f"⚠️ An error occurred: {str(e)}"

# Route to render simple HTML interface
def home(request):
    return render(request, "index.html")

# Route to handle chat requests
def chat(request):
    if request.method == "POST":
        data = request.json
        question = data.get("message", "")
        answer = ask_unani_doctor(question)
        return JsonResponse({"response": answer})
