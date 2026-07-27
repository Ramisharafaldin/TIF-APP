import os
import json
import logging
import time
import hashlib
import google.generativeai as genai
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Optional, Any
from utils.ai_config import ai_config

# Load environment variables
load_dotenv()

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure Gemini API with enhanced error handling
try:
    api_key = ai_config.get_api_key()
    if api_key:
        genai.configure(api_key=api_key)
        logger.info("Gemini API configured successfully")
    else:
        logger.error("Gemini API key not found in environment variables")
        raise ValueError("Missing Gemini API key")
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {e}")
    # Set a flag to disable AI features gracefully
    AI_AVAILABLE = False
else:
    AI_AVAILABLE = True

# Get configuration
config = ai_config.load_api_configuration()
MODEL_NAME = config['model_name']
CACHE_TTL = config['cache_ttl']

# --- Caching Mechanism ---
class InsightsCache:
    def __init__(self, ttl_seconds=None): 
        self.cache = {}
        self.ttl = ttl_seconds or CACHE_TTL

    def _generate_key(self, prompt):
        """Generate cache key with data anonymization."""
        # Anonymize sensitive data in prompt before hashing
        anonymized_prompt = self._anonymize_sensitive_data(prompt)
        return hashlib.md5(anonymized_prompt.encode('utf-8')).hexdigest()

    def _anonymize_sensitive_data(self, prompt: str) -> str:
        """
        Anonymize sensitive data in prompts before caching.
        
        Args:
            prompt: The original prompt
            
        Returns:
            Anonymized prompt with sensitive data masked
        """
        import re
        
        # Mask potential email addresses
        prompt = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', prompt)
        
        # Mask potential phone numbers
        prompt = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', prompt)
        
        # Mask potential credit card numbers
        prompt = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CARD]', prompt)
        
        # Mask potential API keys (but not our own structure)
        prompt = re.sub(r'\b[A-Za-z0-9]{32,}\b', '[API_KEY]', prompt)
        
        return prompt

    def get(self, prompt):
        key = self._generate_key(prompt)
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['timestamp'] < self.ttl:
                logger.info("Cache hit for AI insights prompt")
                return entry['data']
            else:
                del self.cache[key] # Expired
        return None

    def set(self, prompt, data):
        key = self._generate_key(prompt)
        self.cache[key] = {
            'data': data,
            'timestamp': time.time()
        }
        
        # Log cache operation (without sensitive data)
        security_settings = ai_config.get_security_settings()
        if security_settings['log_api_calls']:
            logger.info(f"Cached AI insights response (key: {key[:8]}...)")

    def clear_expired(self):
        """Remove expired cache entries."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time - entry['timestamp'] >= self.ttl
        ]
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"Cleared {len(expired_keys)} expired cache entries")

insights_cache = InsightsCache()

# --- Context Templates ---
class ContextTemplate:
    BASE_INSTRUCTION = """
    You are an AI expert assistant for a Retail Inventory & Sales System.
    Your goal is to provide actionable, data-driven insights.
    Output MUST be valid JSON.
    """

    @staticmethod
    def format_dashboard_prompt(kpis, issues):
        return f"""
        {ContextTemplate.BASE_INSTRUCTION}
        
        ROLE: Senior Business Analyst
        TASK: Analyze Dashboard KPIs.
        
        DATA:
        {json.dumps(kpis, indent=2)}
        
        CONTEXT/ISSUES: {issues or 'None'}

        OUTPUT FORMAT (JSON):
        {{
            "trend_summary": "Brief explanation of performance trend (2 sentences)",
            "anomalies": ["List of detected anomalies"],
            "recommendations": ["Actionable advice 1", "Actionable advice 2", "Actionable advice 3"]
        }}
        """

    @staticmethod
    def format_inventory_prompt(summary):
        return f"""
        {ContextTemplate.BASE_INSTRUCTION}
        
        ROLE: Inventory Management Expert
        TASK: Analyze Stock Health.
        
        DATA:
        {json.dumps(summary, indent=2)}

        OUTPUT FORMAT (JSON):
        {{
            "stock_health": "Comment on overall stock coverage",
            "risks": ["Risk 1 (e.g. dead stock)", "Risk 2"],
            "replenishment_advice": "Specific reorder advice",
            "action_items": ["Step 1", "Step 2"]
        }}
        """

    @staticmethod
    def format_transfer_prompt(transfer_data):
        return f"""
        {ContextTemplate.BASE_INSTRUCTION}
        
        ROLE: Supply Chain Optimization Expert
        TASK: Review Branch Transfer Proposal ("Smart Logistics Engine").
        
        DATA:
        {json.dumps(transfer_data, indent=2)}

        OUTPUT FORMAT (JSON):
        {{
            "transfer_logic_validation": "Validation of the plan",
            "optimization_suggestions": ["Suggestion 1", "Suggestion 2"],
            "priority_moves": ["Critical Move 1", "Critical Move 2"]
        }}
        """

    @staticmethod
    def format_forecast_prompt(forecast_data, historical_context):
        return f"""
        {ContextTemplate.BASE_INSTRUCTION}
        
        ROLE: Demand Planner
        TASK: Review Sales Forecast.
        
        FORECAST DATA: {json.dumps(forecast_data, indent=2)}
        HISTORY: {json.dumps(historical_context or {}, indent=2)}

        OUTPUT FORMAT (JSON):
        {{
            "forecast_validation": "Realistic? (Yes/No + Reason)",
            "trend_analysis": "Expected growth trend description",
            "strategy": "Sales strategy suggestion",
            "confidence_score": 85 (integer 0-100)
        }}
        """

def _call_gemini_api(prompt):
    """
    Helper function to call Gemini API with enhanced error handling, caching and logging.
    
    Args:
        prompt: The prompt to send to the API
        
    Returns:
        Dict containing the API response or error information
    """
    # Check if AI features are available
    if not AI_AVAILABLE:
        logger.warning("AI features are disabled due to configuration issues")
        return {
            "error": "AI features are currently unavailable",
            "details": "Please check API configuration"
        }
    
    # Check cache first
    cached_result = insights_cache.get(prompt)
    if cached_result:
        return cached_result

    start_time = time.time()
    timeout_settings = ai_config.get_timeout_settings()
    security_settings = ai_config.get_security_settings()
    
    try:
        # Log API call (with anonymized data if enabled)
        if security_settings['log_api_calls']:
            anonymized_prompt = insights_cache._anonymize_sensitive_data(prompt[:200] + "..." if len(prompt) > 200 else prompt)
            logger.info(f"Making Gemini API call: {anonymized_prompt}")
        
        model = genai.GenerativeModel(MODEL_NAME)
        
        # Make API call with timeout
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "max_output_tokens": 2048,
                "temperature": 0.1  # Lower temperature for more consistent results
            }
        )
        
        # Parse response
        result = json.loads(response.text)
        
        # Cache the result
        insights_cache.set(prompt, result)
        
        duration = time.time() - start_time
        logger.info(f"Gemini API call successful. Duration: {duration:.2f}s")
        
        # Log successful API interaction for audit
        if security_settings['audit_enabled']:
            _log_api_interaction(prompt, result, duration, success=True)
        
        return result
        
    except json.JSONDecodeError as e:
        duration = time.time() - start_time
        error_msg = f"Failed to parse Gemini API response as JSON: {str(e)}"
        logger.error(error_msg)
        
        # Log failed API interaction for audit
        if security_settings['audit_enabled']:
            _log_api_interaction(prompt, None, duration, success=False, error=error_msg)
        
        return {
            "error": "Invalid response format from AI service",
            "details": "The AI service returned an unexpected response format"
        }
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Gemini API Error: {str(e)}"
        logger.error(error_msg)
        
        # Log failed API interaction for audit
        if security_settings['audit_enabled']:
            _log_api_interaction(prompt, None, duration, success=False, error=error_msg)
        
        # Return fallback structure to prevent UI crashes
        return {
            "error": "Unable to generate insights",
            "details": "The AI service is temporarily unavailable. Please try again later."
        }


def _log_api_interaction(prompt: str, response: Optional[Dict], duration: float, 
                        success: bool, error: Optional[str] = None):
    """
    Log API interactions for audit purposes.
    
    Args:
        prompt: The original prompt (will be anonymized)
        response: The API response (if successful)
        duration: Time taken for the API call
        success: Whether the call was successful
        error: Error message (if failed)
    """
    try:
        # Anonymize prompt for logging
        anonymized_prompt = insights_cache._anonymize_sensitive_data(prompt)
        
        audit_entry = {
            'timestamp': datetime.now().isoformat(),
            'prompt_hash': hashlib.md5(prompt.encode()).hexdigest(),
            'prompt_preview': anonymized_prompt[:100] + "..." if len(anonymized_prompt) > 100 else anonymized_prompt,
            'duration': duration,
            'success': success,
            'model': MODEL_NAME,
            'response_size': len(json.dumps(response)) if response else 0,
            'error': error
        }
        
        # Log to audit file or database (for now, just log to standard logger)
        logger.info(f"AI API Audit: {json.dumps(audit_entry)}")
        
    except Exception as audit_error:
        logger.error(f"Failed to log API interaction for audit: {audit_error}")


def validate_ai_service() -> tuple:
    """
    Validate AI service configuration and connectivity.
    
    Returns:
        Tuple of (is_valid, message)
    """
    try:
        # Check if AI features are enabled
        if not ai_config.is_ai_enabled():
            return False, "AI features are disabled in configuration"
        
        # Validate API key
        is_valid, message = ai_config.validate_api_key()
        if not is_valid:
            return False, message
        
        # Test API connectivity with a simple prompt
        test_prompt = """
        {
            "role": "test",
            "task": "respond with valid JSON",
            "output_format": {"status": "ok", "message": "API connection successful"}
        }
        """
        
        start_time = time.time()
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(
            test_prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        # Try to parse response
        result = json.loads(response.text)
        duration = time.time() - start_time
        
        logger.info(f"AI service validation successful in {duration:.2f}s")
        return True, f"AI service is operational (response time: {duration:.2f}s)"
        
    except Exception as e:
        error_msg = f"AI service validation failed: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

# --- Public Interface ---

def insights_dashboard(kpis, existing_issues=None):
    prompt = ContextTemplate.format_dashboard_prompt(kpis, existing_issues)
    return _call_gemini_api(prompt)

def insights_inventory(inventory_summary):
    prompt = ContextTemplate.format_inventory_prompt(inventory_summary)
    return _call_gemini_api(prompt)

def insights_branch_transfer(transfer_data):
    prompt = ContextTemplate.format_transfer_prompt(transfer_data)
    return _call_gemini_api(prompt)

def insights_sales_forecasting(forecast_data, historical_context=None):
    prompt = ContextTemplate.format_forecast_prompt(forecast_data, historical_context)
    return _call_gemini_api(prompt)
