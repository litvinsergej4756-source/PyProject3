import json
from openai import OpenAI
import os
from dotenv import load_dotenv
from configuration.configurate_logs import setup_logger

load_dotenv()

class ChatgptAiManager:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("❌ OPENAI_API_KEY not found in .env file!")
        self.client = OpenAI(api_key=api_key)

    def generate_description(self, product_name, prompt_text):
        final_prompt = prompt_text.replace("{name}", product_name)

        try:
            response = self.client.chat.completions.create(
                model="gpt-5.1",
                messages=[{"role": "user", "content": final_prompt}],
                temperature=0
            )

            raw_text = response.choices[0].message.content
            clean = raw_text.replace("```json", "").replace("```", "").strip()

            try:
                return json.loads(clean)
            except:
                return {"raw_response": raw_text}

        except Exception as e:
            return {"error": str(e)}
    
    def call_itemdesc_with_browsing(self, prompt_text):
        response = self.client.responses.create(
            model="gpt-5.1",
            input=prompt_text,
            max_output_tokens=4000,
            tools=[
                {
                    # laut aktueller Doku: Web-Suche über Responses API
                    "type": "web_search"
                }
            ],
        )

        try:
            json_text = response.output_text
        except AttributeError:
            # Fallback auf die generische Struktur
            json_text = response.output[0].content[0].text
        
        # Vom Modell geliefertes JSON in Python-Objekt parsen
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            print("Konnte das JSON nicht parsen. Rohtext:")
            print(json_text)
            raise