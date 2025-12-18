import os
from huggingface_hub import InferenceClient
from typing import Dict, Optional, List

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
            
            # Use the shared processing method
            return self._process_single_result(result)
                
        except Exception as e:
            print(f"Error calling Hugging Face API: {e}")
            return {"sentiment": 0, "confidence": 0.0}
    
    def _process_single_result(self, result) -> Dict[str, float]:
        """
        Process a single sentiment analysis result and convert to our format.
        
        Args:
            result: Result from text_classification API
            
        Returns:
            Dictionary with "sentiment" (0 or 1) and "confidence" (0.0 to 1.0)
        """
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
    
    def batch_analyze_sentiment(self, texts: List[str]) -> List[Dict[str, float]]:
        """
        Analyze sentiment for multiple texts using batch processing if supported.
        Falls back to individual processing if batch is not supported.
        
        Args:
            texts: List of texts to analyze
            
        Returns:
            List of dictionaries with "sentiment" (0 or 1) and "confidence" (0.0 to 1.0)
        """
        if not texts:
            return []
        
        # Try batch processing first (if API supports it)
        try:
            result = self.client.text_classification(
                texts,  # Pass list directly
                model="ProsusAI/finbert",
            )
            
            # If batch processing works, result should be a list of results
            if isinstance(result, list):
                # Check if it's a list of results (batch) or a single result
                if len(result) > 0 and isinstance(result[0], list):
                    # Batch result: each element is a list of label/score dicts
                    return [self._process_single_result(r) for r in result]
                elif len(result) > 0 and isinstance(result[0], dict) and 'label' in result[0]:
                    # Single result (API might have processed as single)
                    return [self._process_single_result(result)]
                else:
                    # Unexpected format, fall back to individual
                    raise ValueError("Unexpected batch result format")
            else:
                # Single result, fall back to individual
                raise ValueError("Batch not supported, got single result")
                
        except (TypeError, ValueError, AttributeError) as e:
            # Batch processing not supported or failed, fall back to individual processing
            print(f"Batch processing not supported, falling back to individual processing: {e}")
            results = []
            for text in texts:
                try:
                    result = self.analyze_sentiment(text)
                    results.append(result)
                except Exception as err:
                    print(f"Error analyzing sentiment for text: {err}")
                    results.append({"sentiment": 0, "confidence": 0.0})
            return results
        except Exception as e:
            # Other error, fall back to individual processing
            print(f"Error in batch processing, falling back to individual: {e}")
            results = []
            for text in texts:
                try:
                    result = self.analyze_sentiment(text)
                    results.append(result)
                except Exception as err:
                    print(f"Error analyzing sentiment for text: {err}")
                    results.append({"sentiment": 0, "confidence": 0.0})
            return results

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

