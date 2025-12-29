import os
from dotenv import load_dotenv
from google import genai

# Load env from root
from pathlib import Path
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")

if not api_key:
    print("No API Key found")
    exit(1)

client = genai.Client(api_key=api_key)
try:
    for model in client.models.list(config={"page_size": 100}):
        print(model.name)
except Exception as e:
    print(f"Error listing models: {e}")
