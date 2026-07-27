"""
AI Provider abstraction — shared interface (Phase 3, §4.2).

Every concrete provider (Gemini, OpenAI, Ollama, LM Studio, OpenRouter,
Azure OpenAI, Custom) implements ``AIProviderInterface``. This is the
single contract ``utils/ai_service.py`` depends on, so adding a new
provider requires no changes to the service layer — only a new class and a
factory entry.

Privacy/anonymization is applied by the service layer *before* calling the
provider, so providers never weaken anonymization regardless of whether the
data leaves the machine (e.g. local Ollama). See §4.3 step 7.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime


@dataclass
class AIResponse:
    """Structured AI response with metadata (provider-agnostic)."""
    success: bool
    data: Dict
    error_message: Optional[str]
    confidence_score: Optional[float]
    processing_time: float
    cached: bool
    timestamp: datetime


class AIProviderInterface(ABC):
    """Abstract base for all AI providers."""

    #: Human-readable provider name (e.g. "gemini").
    provider_name: str = "base"

    @abstractmethod
    def validate_connection(self) -> Tuple[bool, str]:
        """Return (is_valid, message) after checking config + connectivity."""
        raise NotImplementedError

    @abstractmethod
    def list_models(self) -> List[str]:
        """Return a list of available model identifiers for this provider."""
        raise NotImplementedError

    @abstractmethod
    def generate_inventory_insights(self, data: Dict, user_id: str = None) -> AIResponse:
        """Generate inventory insights from anonymized data."""
        raise NotImplementedError

    @abstractmethod
    def process_natural_language_query(self, query: str, context: Dict, user_id: str = None) -> AIResponse:
        """Process a natural-language query against anonymized context."""
        raise NotImplementedError

    @abstractmethod
    def generate_smart_report(self, data: Dict, report_type: str, user_id: str = None) -> AIResponse:
        """Generate an AI-enhanced smart report."""
        raise NotImplementedError

    @abstractmethod
    def enhance_forecast(self, forecast_data: Dict, historical_data: Dict, user_id: str = None) -> AIResponse:
        """Enhance a forecast with AI analysis."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Shared prompt builders (providers may override for model specifics)
    # ------------------------------------------------------------------
    def build_insights_prompt(self, data: Dict) -> str:
        import json
        return f"""
You are an AI expert assistant for a Retail Inventory & Sales System.
Your goal is to provide actionable, data-driven insights.
Output MUST be valid JSON.

ROLE: Senior Inventory Analyst
TASK: Analyze inventory data and provide comprehensive insights.

DATA:
{json.dumps(data, indent=2, default=str)}

OUTPUT FORMAT (JSON):
{{
    "stock_health": "Overall assessment of inventory health",
    "critical_items": ["List of items needing immediate attention"],
    "trends": ["Key trends identified in the data"],
    "recommendations": ["Specific actionable recommendations"],
    "risks": ["Potential risks and issues"],
    "opportunities": ["Optimization opportunities"],
    "confidence_score": 85
}}
"""

    def build_query_prompt(self, query: str, context: Dict) -> str:
        import json
        return f"""
You are an AI assistant for inventory management queries.
Process the user's natural language query and provide a helpful response.
Output MUST be valid JSON.

USER QUERY: {query}

AVAILABLE DATA CONTEXT:
{json.dumps(context, indent=2, default=str)}

OUTPUT FORMAT (JSON):
{{
    "intent": "Identified query intent",
    "response": "Natural language response to the query",
    "data_points": ["Relevant data points from context"],
    "suggestions": ["Suggested follow-up questions"],
    "confidence_score": 85
}}
"""

    def build_report_prompt(self, data: Dict, report_type: str) -> str:
        import json
        return f"""
You are an AI business analyst creating enhanced reports.
Generate an intelligent report with insights and recommendations.
Output MUST be valid JSON.

REPORT TYPE: {report_type}

DATA:
{json.dumps(data, indent=2, default=str)}

OUTPUT FORMAT (JSON):
{{
    "executive_summary": "Brief executive summary of key findings",
    "key_metrics": {{"metric_name": "value_and_analysis"}},
    "trends": ["Identified trends and patterns"],
    "insights": ["Key business insights"],
    "recommendations": ["Strategic recommendations"],
    "risk_assessment": "Assessment of potential risks",
    "confidence_score": 85
}}
"""

    def build_forecast_prompt(self, forecast_data: Dict, historical_data: Dict) -> str:
        import json
        return f"""
You are an AI demand planning expert enhancing forecasts.
Analyze the forecast and provide improvements with confidence intervals.
Output MUST be valid JSON.

CURRENT FORECAST:
{json.dumps(forecast_data, indent=2, default=str)}

HISTORICAL CONTEXT:
{json.dumps(historical_data, indent=2, default=str)}

OUTPUT FORMAT (JSON):
{{
    "forecast_validation": "Assessment of current forecast accuracy",
    "confidence_intervals": {{"lower": 0.0, "upper": 0.0}},
    "risk_factors": ["Identified risk factors"],
    "adjustments": ["Suggested forecast adjustments"],
    "external_factors": ["External factors to consider"],
    "recommendations": ["Strategic recommendations"],
    "confidence_score": 85
}}
"""

    @staticmethod
    def calculate_confidence(result: Any) -> Optional[float]:
        """Extract a confidence score from a provider result dict."""
        if isinstance(result, dict):
            return result.get('confidence_score', 75.0)
        return None
