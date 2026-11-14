import os
from google import genai
from google.genai import types
from src.config import MODEL_NAME

def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Transcribe raw audio bytes using Gemini."""
    api_key = os.getenv("GEMINI_API_KEY")
    try:
        client = genai.Client(api_key=api_key) if api_key else genai.Client()
    except Exception as e:
        print(f"Could not initialize genai client for transcription: {e}")
        return ""

    prompt = "You are an expert sales assistant. Please provide a highly accurate, word-for-word transcription of this meeting audio. Only output the transcription, nothing else."
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                prompt
            ]
        )
        return response.text.strip()
    except Exception as e:
        print(f"Error during transcription: {e}")
        return ""
