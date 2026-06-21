import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class Researcher:
    def __init__(self, model_name="gemini-2.5-flash"):
        self.client = genai.Client()
        self.model_name = model_name
        self.system_instruction = "You are a financial researcher. Extract the exact figure requested from the source text. Keep your answer brief and include the number."
        
    def extract_figure(self, source_text: str, question: str, memory_context: str = "") -> str:
        memory_prompt = f"Historical Memory:\n{memory_context}\n\n" if memory_context else ""
        prompt = f"{memory_prompt}Source text:\n{source_text}\n\nQuestion:\n{question}\n\nExtract the exact number. Be concise."
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                temperature=0.0
            )
        )
        return response.text

class Analyst:
    def __init__(self, model_name="gemini-2.5-flash"):
        self.client = genai.Client()
        self.model_name = model_name
        self.system_instruction = "You are a financial analyst. Calculate derived metrics based on the provided data and historical memory. Keep your answer brief and include the derived number."
        
    def derive_insight(self, raw_fact: str, context: str, memory_context: str = "") -> str:
        memory_prompt = f"Historical Memory:\n{memory_context}\n\n" if memory_context else ""
        prompt = f"{memory_prompt}Background Context:\n{context}\n\nGiven this raw fact:\n{raw_fact}\n\nProvide a derived insight (e.g., Year-over-Year growth, margin percentage). Be concise and state the derived number clearly. Rely on the historical memory if historical baseline figures are needed to calculate the derivation."
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                temperature=0.0
            )
        )
        return response.text

class Writer:
    def __init__(self, model_name="gemini-2.5-flash"):
        self.client = genai.Client()
        self.model_name = model_name
        self.system_instruction = "You are a financial writer. Draft a concise narrative sentence incorporating the provided insight."
        
    def draft_narrative(self, derived_insight: str) -> str:
        prompt = f"Insight:\n{derived_insight}\n\nDraft a single, professional narrative sentence for an earnings report that includes this insight."
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                temperature=0.0
            )
        )
        return response.text

class Reviewer:
    def __init__(self, model_name="gemini-2.5-flash"):
        self.client = genai.Client()
        self.model_name = model_name
        self.system_instruction = "You are an internal reviewer. Check the narrative for grammatical consistency and professional tone. Do NOT verify the numbers against source documents. Just output the approved sentence."
        
    def review(self, narrative: str) -> str:
        prompt = f"Narrative to review:\n{narrative}\n\nReview this for professional tone. Return the final polished sentence. Do not add conversational filler."
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                temperature=0.0
            )
        )
        return response.text
