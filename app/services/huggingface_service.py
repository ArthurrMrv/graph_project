import os
from huggingface_hub import InferenceClient
from typing import Dict, Optional

class HuggingFaceService:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Hugging Face Inference Client.
        
        Args:
            api_key: Optional HF_TOKEN. If not provided, will try to get from environment.
        """
        if api_key is None or api_key == "string" or api_key == "":
            api_key = os.getenv("HF_TOKEN")
        if api_key is None or api_key == "":
            raise ValueError("HF_TOKEN must be provided either as parameter or in environment variable")
        
        self.api_key = api_key
        
        print(f"Using API key: {api_key}")
        
        self.client = InferenceClient(
            provider="hf-inference",
            api_key=api_key,
        )
    
    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment using ProsusAI/finbert model.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with "sentiment" (0 or 1) and "confidence" (0.0 to 1.0)
        """
        try:
            result = self.client.text_classification(
                text,
                model="ProsusAI/finbert",
            )
            
            # result is a list of dicts with 'label' and 'score'
            # finbert typically returns: positive, negative, neutral
            # Map to our format: sentiment (0/1) and confidence (0.0-1.0)
            
            print(result)
            # Find the highest scoring label
            if isinstance(result, list) and len(result) > 0:
                # Sort by score descending
                sorted_results = sorted(result, key=lambda x: x.get('score', 0), reverse=True)
                top_result = sorted_results[0]
                
                label = top_result.get('label', '').lower()
                score = top_result.get('score', 0.0)
                
                # Map label to sentiment: positive -> 1, negative/neutral -> 0
                sentiment = 1 if label == 'positive' else 0
                
                # Use the score as confidence, but if sentiment is positive and confidence < 0.5, return sentiment 0
                confidence = float(score)
                if sentiment == 1 and confidence < 0.5:
                    sentiment = 0
                
                return {
                    "sentiment": sentiment,
                    "confidence": confidence
                }
            else:
                # Fallback if result format is unexpected
                return {"sentiment": 0, "confidence": 0.0}
                
        except Exception as e:
            print(f"Error calling Hugging Face API: {e}")
            return {"sentiment": 0, "confidence": 0.0}

# Cache for default service (using env HF_TOKEN)
_default_service: Optional[HuggingFaceService] = None

def get_hf_service(api_key: Optional[str] = None) -> HuggingFaceService:
    """
    Get or create Hugging Face service instance.
    
    Args:
        api_key: Optional API key. If not provided, will use HF_TOKEN from env.
                 If provided, creates a new instance. If None and env has HF_TOKEN,
                 returns cached default instance.
        
    Returns:
        HuggingFaceService instance
    """
    global _default_service
    
    # If api_key is provided, create a new instance with that key
    if api_key is not None:
        return HuggingFaceService(api_key=api_key)
    
    # Otherwise, use cached default service (from env) or create it
    if _default_service is None:
        _default_service = HuggingFaceService(api_key=None)  # Will use env HF_TOKEN
    return _default_service

