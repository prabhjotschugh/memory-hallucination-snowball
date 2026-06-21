import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class Researcher:
    def __init__(self, model_name="gemini-2.5-flash"):
        self.client = genai.Client() # Automatically picks up GEMINI_API_KEY from environment
        self.model_name = model_name
        self.system_instruction = "You are a financial researcher. Extract the exact figure requested from the source text. Keep your answer brief and include the number."
        
    def extract_figure(self, source_text: str, question: str) -> str:
        prompt = f"Source text:\n{source_text}\n\nQuestion:\n{question}\n\nExtract the exact number. Be concise."
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.system_instruction,
            )
        )
        return response.text
