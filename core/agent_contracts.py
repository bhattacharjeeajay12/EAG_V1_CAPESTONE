# core/agent_contracts.py
"""
Agent Contracts - Input/Output Schemas and Agent Invocation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Literal
from datetime import datetime
import json


@dataclass
class AgentRequest:
    """
    Standardized request format for all agents.
    """
    trace_id: str
    context: Dict[str, Any]
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "context": self.context,
            "parameters": self.parameters,
            "timeout": self.timeout,
            "metadata": self.metadata,
            "timestamp": datetime.now().isoformat()
        }


@dataclass
class AgentResponse:
    """
    Standardized response format for all agents.
    """
    status: Literal["success", "failure", "partial"]
    result: Dict[str, Any] = field(default_factory=dict)
    context_updates: Dict[str, Any] = field(default_factory=dict)
    next_actions: List[str] = field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status,
            "result": self.result,
            "context_updates": self.context_updates,
            "next_actions": self.next_actions,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": datetime.now().isoformat()
        }


class AgentValidator:
    """
    Validates agent requests and responses against expected schemas.
    """

    @staticmethod
    def validate_request(agent_type: str, request: AgentRequest) -> Dict[str, Any]:
        """
        Validate agent request before invocation.

        Args:
            agent_type: Type of agent
            request: Request to validate

        Returns:
            Validation result with errors if any
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        # Basic request validation
        if not request.trace_id:
            validation_result["errors"].append("Missing trace_id")

        if not isinstance(request.context, dict):
            validation_result["errors"].append("Context must be a dictionary")

        # Agent-specific validation
        agent_requirements = AgentValidator._get_agent_requirements(agent_type)

        for required_key in agent_requirements.get("required_context", []):
            if required_key not in request.context or request.context[required_key] is None:
                validation_result["errors"].append(f"Missing required context: {required_key}")

        for optional_key in agent_requirements.get("optional_context", []):
            if optional_key not in request.context:
                validation_result["warnings"].append(f"Optional context missing: {optional_key}")

        validation_result["valid"] = len(validation_result["errors"]) == 0
        return validation_result

    @staticmethod
    def validate_response(agent_type: str, response: AgentResponse) -> Dict[str, Any]:
        """
        Validate agent response after execution.

        Args:
            agent_type: Type of agent
            response: Response to validate

        Returns:
            Validation result
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        # Basic response validation
        if response.status not in ["success", "failure", "partial"]:
            validation_result["errors"].append(f"Invalid status: {response.status}")

        if response.status == "failure" and not response.error:
            validation_result["warnings"].append("Failure status but no error message")

        # Agent-specific response validation
        agent_requirements = AgentValidator._get_agent_requirements(agent_type)

        if response.status == "success":
            for expected_output in agent_requirements.get("expected_outputs", []):
                if expected_output not in response.result:
                    validation_result["warnings"].append(f"Missing expected output: {expected_output}")

        validation_result["valid"] = len(validation_result["errors"]) == 0
        return validation_result

    @staticmethod
    def _get_agent_requirements(agent_type: str) -> Dict[str, Any]:
        """Get requirements for specific agent type."""
        requirements = {
            "BUY": {
                "required_context": ["intent"],
                "optional_context": ["category", "subcategory", "budget", "preferences"],
                "expected_outputs": ["search_results", "product_options"]
            },
            "ORDER": {
                "required_context": ["order_id"],
                "optional_context": ["user_id"],
                "expected_outputs": ["order_details", "order_status"]
            },
            "RECOMMEND": {
                "required_context": ["category"],
                "optional_context": ["budget", "preferences", "comparison_items"],
                "expected_outputs": ["recommendations", "reasoning"]
            },
            "RETURN": {
                "required_context": ["order_id"],
                "optional_context": ["return_reason", "items"],
                "expected_outputs": ["return_status", "return_id"]
            }
        }

        return requirements.get(agent_type, {
            "required_context": [],
            "optional_context": [],
            "expected_outputs": []
        })


class AgentInvoker:
    """
    Handles agent invocation with validation, logging, and error handling.
    """

    def __init__(self):
        """Initialize agent invoker."""
        self.invocation_log = []
        self.validator = AgentValidator()

        # Mock agent registry for testing
        self.mock_agents = {
            "BUY": self._mock_buy_agent,
            "ORDER": self._mock_order_agent,
            "RECOMMEND": self._mock_recommend_agent,
            "RETURN": self._mock_return_agent
        }

    def invoke_agent(self, agent_type: str, request: AgentRequest) -> AgentResponse:
        """
        Invoke an agent with full validation and logging.

        Args:
            agent_type: Type of agent to invoke
            request: Request to send to agent

        Returns:
            Agent response
        """
        start_time = datetime.now()

        # Step 1: Validate request
        validation = self.validator.validate_request(agent_type, request)

        if not validation["valid"]:
            error_response = AgentResponse(
                status="failure",
                error=f"Request validation failed: {', '.join(validation['errors'])}",
                metadata={"validation_errors": validation["errors"]}
            )
            self._log_invocation(agent_type, request, error_response, start_time, datetime.now())
            return error_response

        try:
            # Step 2: Invoke agent (mock implementation)
            if agent_type in self.mock_agents:
                response = self.mock_agents[agent_type](request)
            else:
                response = AgentResponse(
                    status="failure",
                    error=f"Unknown agent type: {agent_type}"
                )

            # Step 3: Validate response
            response_validation = self.validator.validate_response(agent_type, response)
            if response_validation["warnings"]:
                response.metadata["validation_warnings"] = response_validation["warnings"]

            end_time = datetime.now()

            # Step 4: Log invocation
            self._log_invocation(agent_type, request, response, start_time, end_time)

            return response

        except Exception as e:
            end_time = datetime.now()
            error_response = AgentResponse(
                status="failure",
                error=f"Agent invocation error: {str(e)}",
                metadata={"exception_type": type(e).__name__}
            )

            self._log_invocation(agent_type, request, error_response, start_time, end_time)
            return error_response

    def _log_invocation(self, agent_type: str, request: AgentRequest, response: AgentResponse,
                        start_time: datetime, end_time: datetime) -> None:
        """Log agent invocation details."""
        log_entry = {
            "timestamp": start_time.isoformat(),
            "agent_type": agent_type,
            "trace_id": request.trace_id,
            "request_size": len(json.dumps(request.to_dict())),
            "response_status": response.status,
            "response_size": len(json.dumps(response.to_dict())),
            "duration_ms": int((end_time - start_time).total_seconds() * 1000),
            "success": response.status == "success"
        }

        self.invocation_log.append(log_entry)

    def get_invocation_stats(self) -> Dict[str, Any]:
        """Get statistics about agent invocations."""
        if not self.invocation_log:
            return {"total_invocations": 0}

        total = len(self.invocation_log)
        successful = sum(1 for log in self.invocation_log if log["success"])

        agent_counts = {}
        total_duration = 0

        for log in self.invocation_log:
            agent_type = log["agent_type"]
            agent_counts[agent_type] = agent_counts.get(agent_type, 0) + 1
            total_duration += log["duration_ms"]

        return {
            "total_invocations": total,
            "successful_invocations": successful,
            "success_rate": successful / total if total > 0 else 0,
            "average_duration_ms": total_duration / total if total > 0 else 0,
            "agent_usage": agent_counts
        }

    # Mock agent implementations for testing
    def _mock_buy_agent(self, request: AgentRequest) -> AgentResponse:
        """Mock BUY agent implementation."""
        context = request.context

        if context.get("category") and context.get("subcategory"):
            return AgentResponse(
                status="success",
                result={
                    "search_results": [
                        {"name": f"Sample {context['subcategory']}", "price": "$299"},
                        {"name": f"Premium {context['subcategory']}", "price": "$599"}
                    ],
                    "product_count": 2
                },
                context_updates={"products_searched": True},
                next_actions=["select_product"]
            )
        else:
            return AgentResponse(
                status="failure",
                error="Missing category or subcategory for product search"
            )

    def _mock_order_agent(self, request: AgentRequest) -> AgentResponse:
        """Mock ORDER agent implementation."""
        context = request.context

        if context.get("order_id"):
            return AgentResponse(
                status="success",
                result={
                    "order_details": {
                        "order_id": context["order_id"],
                        "status": "shipped",
                        "items": ["Sample Product"]
                    }
                },
                context_updates={"order_found": True}
            )
        else:
            return AgentResponse(
                status="failure",
                error="Order ID required for order lookup"
            )

    def _mock_recommend_agent(self, request: AgentRequest) -> AgentResponse:
        """Mock RECOMMEND agent implementation."""
        context = request.context

        if context.get("category"):
            return AgentResponse(
                status="success",
                result={
                    "recommendations": [
                        {"name": f"Top {context['category']} Choice", "rating": 4.8},
                        {"name": f"Budget {context['category']} Option", "rating": 4.2}
                    ],
                    "reasoning": "Based on popularity and reviews"
                },
                context_updates={"recommendations_generated": True}
            )
        else:
            return AgentResponse(
                status="failure",
                error="Category required for recommendations"
            )

    def _mock_return_agent(self, request: AgentRequest) -> AgentResponse:
        """Mock RETURN agent implementation."""
        context = request.context

        if context.get("order_id"):
            return AgentResponse(
                status="success",
                result={
                    "return_id": f"RET_{context['order_id']}_001",
                    "return_status": "approved",
                    "refund_amount": "$299"
                },
                context_updates={"return_initiated": True}
            )
        else:
            return AgentResponse(
                status="failure",
                error="Order ID required for return processing"
            )


# Test code for agent contracts
def test_agent_contracts():
    """Test agent contracts and invocation system."""
    print("🧪 Testing Agent Contracts")
    print("=" * 50)

    # Create agent invoker
    invoker = AgentInvoker()

    # Test BUY agent
    print("🛒 Testing BUY Agent:")
    buy_request = AgentRequest(
        trace_id="test_buy_001",
        context={
            "intent": "BUY",
            "category": "electronics",
            "subcategory": "laptop",
            "budget": "under $1000"
        },
        parameters={"search_limit": 10}
    )

    buy_response = invoker.invoke_agent("BUY", buy_request)
    print(f"  Status: {buy_response.status}")
    print(f"  Results: {len(buy_response.result.get('search_results', []))} products found")

    # Test ORDER agent
    print("\n📦 Testing ORDER Agent:")
    order_request = AgentRequest(
        trace_id="test_order_001",
        context={"order_id": "ORD12345"},
        parameters={}
    )

    order_response = invoker.invoke_agent("ORDER", order_request)
    print(f"  Status: {order_response.status}")
    if order_response.status == "success":
        order_details = order_response.result.get("order_details", {})
        print(f"  Order Status: {order_details.get('status', 'unknown')}")

    # Test validation failure
    print("\n❌ Testing Validation Failure:")
    invalid_request = AgentRequest(
        trace_id="test_invalid",
        context={},  # Missing required fields
        parameters={}
    )

    invalid_response = invoker.invoke_agent("ORDER", invalid_request)
    print(f"  Status: {invalid_response.status}")
    print(f"  Error: {invalid_response.error}")

    # Show invocation stats
    print("\n📊 Invocation Statistics:")
    stats = invoker.get_invocation_stats()
    print(f"  Total invocations: {stats['total_invocations']}")
    print(f"  Success rate: {stats['success_rate']:.1%}")
    print(f"  Average duration: {stats['average_duration_ms']:.1f}ms")
    print(f"  Agent usage: {stats['agent_usage']}")

    print("\n" + "=" * 50)
    print("✅ Agent Contracts Test Complete!")


if __name__ == "__main__":
    test_agent_contracts()