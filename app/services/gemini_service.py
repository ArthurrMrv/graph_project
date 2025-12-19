import json
import google.generativeai as genai


class GeminiService:
    def analyze_sentiment(self, text: str, api_key: str):
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
        Analyze the sentiment of the following financial tweet.
        Return a JSON object with:
        - "sentiment": 1 if positive, 0 if negative.
        - "confidence": A score between 0.0 and 1.0. 
        If sentiment is positive but confidence is < 0.5, return sentimet 0.
        
        Tweet: "{text}"
        
        Do not include markdown formatting in the response, just the raw JSON.
        """

        try:
            response = model.generate_content(prompt)
            # Basic cleanup if model returns markdown ticks
            clean_text = response.text.strip().replace("```json", "").replace("```", "")
            data = json.loads(clean_text)
            return data
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Error calling Gemini: {e}")
            return {"sentiment": 0, "confidence": 0.0}


gemini_service = GeminiService()
