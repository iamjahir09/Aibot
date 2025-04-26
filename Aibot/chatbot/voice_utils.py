import io
import speech_recognition as sr
import pyttsx3

class UnaniVoiceAssistant:
    def __init__(self):
        """Initialize voice assistant with speech recognition and text-to-speech"""
        self.recognizer = sr.Recognizer()
        self.engine = self._initialize_tts_engine()
        
    def _initialize_tts_engine(self):
        """Configure text-to-speech engine with Hindi/Urdu voice"""
        engine = pyttsx3.init()
        
        # Set Hindi/Urdu voice if available
        voices = engine.getProperty('voices')
        for voice in voices:
            if any(lang in voice.name.lower() for lang in ['hindi', 'urdu', 'indian']):
                engine.setProperty('voice', voice.id)
                break
        
        # Configure speech settings
        engine.setProperty('rate', 150)  # Medium speech speed
        engine.setProperty('volume', 0.9)  # Slightly less than max volume
        return engine

    def process_audio(self, audio_stream):
        """Convert audio stream to text using Google Speech Recognition"""
        try:
            with sr.AudioFile(audio_stream) as source:
                audio = self.recognizer.record(source)
                return self.recognizer.recognize_google(audio, language='hi-IN')
        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand audio")
            return None
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")
            return None
        except Exception as e:
            print(f"Audio processing error: {e}")
            return None

    def speak(self, text):
        """Convert text to speech"""
        try:
            self.engine.stop()  # Stop any ongoing speech
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            print(f"Text-to-speech error: {e}")