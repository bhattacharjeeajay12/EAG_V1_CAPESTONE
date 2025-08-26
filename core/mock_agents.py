# core/mock_agents.py
"""
Mock Agent Manager - Realistic Agent Simulations with Discovery Agent

Purpose: Provides realistic mock implementations of all agents including the new
Discovery Agent. The Discovery Agent uses dual-mode logic to provide both
search and recommendation capabilities based on user specificity.

Available Agents:
- DiscoveryAgent: Dual-mode product discovery (search-first vs recommend-first)
- OrderAgent: Order tracking, status updates, modification handling
- ReturnAgent: Return processing, refund handling, exchange management
"""

import random
from typing import Dict, List, Any, Optional
from datetime import datetime
from agents.discovery_agent import DiscoveryAgent, DiscoveryRequest, UserSpecificity


class MockAgentManager:
    """
    Centralized manager for all mock agents with realistic data generation.
    """

    def __init__(self):
        """Initialize mock agent manager with sample data."""
        self.sample_products = self._initialize_sample_products()
        self.sample_orders = self._initialize_sample_orders()

        # Initialize Discovery Agent with product database
        self.discovery_agent = DiscoveryAgent(self.sample_products)

    def call_agent(self, agent_type: str, params: Dict[str, Any],
                   context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route agent calls to appropriate mock implementations.

        Args:
            agent_type: Type of agent to call
            params: Parameters for the agent
            context: Current conversation context

        Returns:
            Agent response exactly as real agent would return
        """
        agent_methods = {
            "DiscoveryAgent": self._mock_discovery_agent,
            "OrderAgent": self._mock_order_agent,
            "ReturnAgent": self._mock_return_agent
        }

        if agent_type not in agent_methods:
            return self._create_error_response(f"Unknown agent type: {agent_type}")

        try:
            return agent_methods[agent_type](params, context)
        except Exception as e:
            return self._create_error_response(f"Agent {agent_type} error: {str(e)}")

    def _mock_discovery_agent(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Mock Discovery Agent - handles dual-mode product discovery."""

        # Extract parameters
        category = params.get("category", "electronics")
        subcategory = params.get("subcategory", "")
        specifications = params.get("specifications", {})
        budget = params.get("budget")
        user_message = params.get("user_message", "")
        discovery_mode = params.get("discovery_mode", "auto")

        if not subcategory:
            return {
                "status": "missing_info",
                "user_message": "I need to know what specific product category you're interested in. Could you be more specific?",
                "discovery_performed": False,
                "required_info": ["subcategory"]
            }

        # Determine user specificity and discovery mode if auto
        if discovery_mode == "auto":
            user_specificity, determined_mode = self.discovery_agent.determine_user_specificity(
                {"specifications": specifications, "budget": budget},
                user_message
            )
        else:
            user_specificity = UserSpecificity.MODERATE
            determined_mode = discovery_mode

        # Create discovery request
        discovery_request = DiscoveryRequest(
            category=category,
            subcategory=subcategory,
            specifications=specifications,
            budget=budget,
            user_specificity=user_specificity,
            discovery_mode=determined_mode,
            use_case=params.get("use_case"),
            preferences=params.get("preferences", [])
        )

        # Execute discovery
        discovery_result = self.discovery_agent.discover_products(discovery_request)

        # Format response for planner
        return {
            "status": discovery_result.status,
            "discovery_mode": discovery_result.discovery_mode.value,
            "user_specificity": user_specificity.value,
            "products_found": discovery_result.total_found,
            "search_results": discovery_result.search_results,
            "recommendations": discovery_result.recommendations,
            "user_message": discovery_result.user_message,
            "next_actions": discovery_result.next_actions,
            "refinement_suggestions": discovery_result.refinement_suggestions or [],
            "discovery_performed": True,
            "search_criteria": {
                "category": category,
                "subcategory": subcategory,
                "specifications": specifications,
                "budget": budget
            }
        }

    def _mock_order_agent(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Mock Order Agent - handles order tracking and management."""

        order_id = params.get("order_id")
        action = params.get("action", "track")  # track, modify, cancel

        if not order_id:
            # Try to extract from user context or show recent orders
            user_orders = self._get_user_recent_orders(context)
            if user_orders:
                return {
                    "status": "order_selection",
                    "recent_orders": user_orders,
                    "user_message": "I found your recent orders. Which one are you asking about?\n" +
                                    "\n".join([
                                                  f"• Order {order['order_id']} - {order['items'][0]['name']} (${order['total_amount']})"
                                                  for order in user_orders[:5]]),
                    "order_lookup_performed": True,
                    "requires_selection": True
                }
            else:
                return {
                    "status": "missing_info",
                    "error": "Order ID required",
                    "user_message": "I need your order ID to help you. Could you provide your order number?",
                    "order_lookup_performed": False
                }

        # Simulate order lookup
        order_info = self._lookup_mock_order(order_id)

        if not order_info:
            return {
                "status": "not_found",
                "order_id": order_id,
                "user_message": f"I couldn't find order {order_id}. Please check the order number and try again.",
                "order_lookup_performed": True,
                "suggestions": ["Double-check the order number", "Check your email for order confirmation"]
            }

        if action == "track":
            return {
                "status": "success",
                "order_info": order_info,
                "tracking_info": {
                    "current_status": order_info["status"],
                    "estimated_delivery": order_info["estimated_delivery"],
                    "tracking_number": order_info.get("tracking_number"),
                    "carrier": order_info.get("carrier", "Standard Shipping")
                },
                "user_message": self._create_order_status_message(order_info),
                "order_lookup_performed": True,
                "actions_available": ["track_shipment", "modify_order", "contact_support"]
            }

        elif action == "modify":
            return {
                "status": "modification_info",
                "order_info": order_info,
                "modification_options": self._get_modification_options(order_info),
                "user_message": f"Here are the modification options available for order {order_id}:",
                "order_lookup_performed": True
            }

        else:
            return {
                "status": "action_completed",
                "order_id": order_id,
                "action": action,
                "user_message": f"I've processed your {action} request for order {order_id}.",
                "order_lookup_performed": True
            }

    def _mock_return_agent(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Mock Return Agent - processes returns and refunds."""

        order_id = params.get("order_id")
        return_reason = params.get("return_reason", "not_specified")
        items_to_return = params.get("items", [])

        if not order_id:
            # Show user's returnable orders
            returnable_orders = self._get_returnable_orders(context)
            if returnable_orders:
                return {
                    "status": "order_selection",
                    "returnable_orders": returnable_orders,
                    "user_message": "Here are your recent orders that can be returned:\n" +
                                    "\n".join([f"• Order {order['order_id']} - {order['items'][0]['name']} "
                                               f"(Ordered: {order['order_date']})"
                                               for order in returnable_orders[:5]]) +
                                    "\n\nWhich order would you like to return?",
                    "return_initiated": False,
                    "requires_selection": True
                }
            else:
                return {
                    "status": "missing_info",
                    "user_message": "I need your order ID to process the return. What's your order number?",
                    "return_initiated": False,
                    "required_info": ["order_id", "return_reason"]
                }

        # Look up order for return eligibility
        order_info = self._lookup_mock_order(order_id)

        if not order_info:
            return {
                "status": "order_not_found",
                "order_id": order_id,
                "user_message": f"I couldn't find order {order_id}. Please verify the order number.",
                "return_initiated": False
            }

        # Check return eligibility
        eligibility = self._check_return_eligibility(order_info)

        if not eligibility["eligible"]:
            return {
                "status": "not_eligible",
                "order_info": order_info,
                "eligibility_info": eligibility,
                "user_message": f"Unfortunately, order {order_id} is not eligible for return. {eligibility['reason']}",
                "return_initiated": False,
                "alternatives": eligibility.get("alternatives", [])
            }

        # Process return
        return_info = self._process_mock_return(order_info, return_reason, items_to_return)

        return {
            "status": "return_processed",
            "return_info": return_info,
            "order_info": order_info,
            "estimated_refund_amount": return_info["refund_amount"],
            "return_tracking": return_info["return_tracking"],
            "user_message": self._create_return_confirmation_message(return_info),
            "return_initiated": True,
            "next_steps": return_info["next_steps"]
        }

    def _initialize_sample_products(self) -> List[Dict[str, Any]]:
        """Initialize sample product database."""
        return [
            {
                "id": "laptop_001",
                "name": "Dell Gaming Laptop G15",
                "category": "electronics",
                "subcategory": "laptop",
                "price": 1299,
                "brand": "Dell",
                "specifications": ["gaming", "nvidia_rtx", "16gb_ram", "ssd"],
                "rating": 4.5,
                "in_stock": True,
                "description": "High-performance gaming laptop with RTX 3060"
            },
            {
                "id": "laptop_002",
                "name": "MacBook Pro M3",
                "category": "electronics",
                "subcategory": "laptop",
                "price": 1999,
                "brand": "Apple",
                "specifications": ["professional", "m3_chip", "16gb_ram", "retina_display"],
                "rating": 4.8,
                "in_stock": True,
                "description": "Professional laptop with Apple M3 chip"
            },
            {
                "id": "laptop_003",
                "name": "HP Pavilion Business Laptop",
                "category": "electronics",
                "subcategory": "laptop",
                "price": 899,
                "brand": "HP",
                "specifications": ["business", "intel_i5", "8gb_ram", "lightweight"],
                "rating": 4.2,
                "in_stock": True,
                "description": "Reliable business laptop with long battery life"
            },
            {
                "id": "phone_001",
                "name": "iPhone 15 Pro",
                "category": "electronics",
                "subcategory": "smartphone",
                "price": 999,
                "brand": "Apple",
                "specifications": ["photography", "a17_chip", "titanium", "usb_c"],
                "rating": 4.7,
                "in_stock": True,
                "description": "Latest iPhone with advanced camera system"
            },
            {
                "id": "phone_002",
                "name": "Samsung Galaxy S24",
                "category": "electronics",
                "subcategory": "smartphone",
                "price": 899,
                "brand": "Samsung",
                "specifications": ["photography", "ai_features", "5g", "fast_charging"],
                "rating": 4.6,
                "in_stock": True,
                "description": "Android flagship with AI photography"
            },
            {
                "id": "headphones_001",
                "name": "Sony WH-1000XM5",
                "category": "electronics",
                "subcategory": "headphones",
                "price": 399,
                "brand": "Sony",
                "specifications": ["noise_cancelling", "wireless", "30h_battery"],
                "rating": 4.6,
                "in_stock": True,
                "description": "Premium noise-cancelling headphones"
            }
        ]

    def _initialize_sample_orders(self) -> List[Dict[str, Any]]:
        """Initialize sample order database."""
        return [
            {
                "order_id": "12345",
                "status": "shipped",
                "items": [{"name": "Dell Gaming Laptop G15", "quantity": 1, "price": 1299}],
                "total_amount": 1299,
                "order_date": "2024-12-20",
                "estimated_delivery": "2024-12-28",
                "tracking_number": "TRK123456789",
                "carrier": "FedEx"
            },
            {
                "order_id": "67890",
                "status": "delivered",
                "items": [{"name": "iPhone 15 Pro", "quantity": 1, "price": 999}],
                "total_amount": 999,
                "order_date": "2024-12-15",
                "delivery_date": "2024-12-22",
                "tracking_number": "TRK987654321"
            },
            {
                "order_id": "URGENT123",
                "status": "processing",
                "items": [{"name": "Sony Headphones", "quantity": 1, "price": 399}],
                "total_amount": 399,
                "order_date": "2024-12-25",
                "estimated_delivery": "2024-12-30"
            },
            {
                "order_id": "ORD456",
                "status": "delivered",
                "items": [{"name": "MacBook Pro M3", "quantity": 1, "price": 1999}],
                "total_amount": 1999,
                "order_date": "2024-12-10",
                "delivery_date": "2024-12-18",
                "tracking_number": "TRK111222333"
            }
        ]

    def _get_user_recent_orders(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get user's recent orders from context or mock data."""
        # In real implementation, this would fetch from user's order history
        # For mock, return sample orders
        return self.sample_orders[-3:]  # Return 3 most recent orders

    def _get_returnable_orders(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get user's orders eligible for return."""
        # Filter orders that can be returned (delivered within return window)
        returnable = []
        for order in self.sample_orders:
            if order["status"] == "delivered":
                order_date = datetime.strptime(order["order_date"], "%Y-%m-%d")
                days_since = (datetime.now() - order_date).days
                if days_since <= 30:  # 30-day return window
                    returnable.append(order)
        return returnable

    def _lookup_mock_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Look up order in mock database."""
        for order in self.sample_orders:
            if order["order_id"] == order_id:
                return order
        return None

    def _check_return_eligibility(self, order_info: Dict[str, Any]) -> Dict[str, Any]:
        """Check if order is eligible for return."""

        order_date = datetime.strptime(order_info["order_date"], "%Y-%m-%d")
        days_since_order = (datetime.now() - order_date).days

        if order_info["status"] == "delivered":
            if days_since_order <= 30:
                return {"eligible": True, "reason": "Within return window"}
            else:
                return {
                    "eligible": False,
                    "reason": "Return window expired (30 days)",
                    "alternatives": ["Contact customer service for special consideration"]
                }
        elif order_info["status"] in ["shipped", "processing"]:
            return {"eligible": True, "reason": "Order can be cancelled/returned"}
        else:
            return {"eligible": False, "reason": "Order status not eligible for return"}

    def _process_mock_return(self, order_info: Dict[str, Any], reason: str,
                             items: List[str]) -> Dict[str, Any]:
        """Process return and generate return information."""

        return_id = f"RET{random.randint(100000, 999999)}"
        refund_amount = order_info["total_amount"]

        return {
            "return_id": return_id,
            "order_id": order_info["order_id"],
            "return_reason": reason,
            "items_returned": items or ["All items"],
            "refund_amount": refund_amount,
            "refund_method": "Original payment method",
            "estimated_refund_time": "5-7 business days",
            "return_tracking": {
                "return_label_generated": True,
                "return_address_provided": True,
                "prepaid_shipping": True
            },
            "next_steps": [
                "Package items securely",
                "Print return label (sent to email)",
                "Drop off at nearest shipping location",
                "Track return progress online"
            ]
        }

    def _create_order_status_message(self, order_info: Dict[str, Any]) -> str:
        """Create user-friendly order status message."""

        status = order_info["status"]
        order_id = order_info["order_id"]

        if status == "processing":
            return f"Your order {order_id} is currently being processed. Estimated delivery: {order_info.get('estimated_delivery', 'TBD')}."

        elif status == "shipped":
            tracking = order_info.get("tracking_number", "No tracking available")
            carrier = order_info.get("carrier", "Standard shipping")
            return (f"Good news! Order {order_id} has shipped via {carrier}. "
                    f"Tracking number: {tracking}. "
                    f"Estimated delivery: {order_info.get('estimated_delivery', 'TBD')}.")

        elif status == "delivered":
            delivery_date = order_info.get("delivery_date", "recently")
            return f"Order {order_id} was successfully delivered on {delivery_date}. Enjoy your purchase!"

        else:
            return f"Order {order_id} status: {status}. Contact support if you have questions."

    def _create_return_confirmation_message(self, return_info: Dict[str, Any]) -> str:
        """Create user-friendly return confirmation message."""

        return_id = return_info["return_id"]
        refund_amount = return_info["refund_amount"]
        refund_time = return_info["estimated_refund_time"]

        return (f"Your return has been processed! Return ID: {return_id}. "
                f"You'll receive a ${refund_amount} refund within {refund_time}. "
                f"A return shipping label has been sent to your email. "
                f"Simply package the items and drop them off at any shipping location.")

    def _get_modification_options(self, order_info: Dict[str, Any]) -> List[str]:
        """Get available modification options for an order."""

        status = order_info["status"]

        if status == "processing":
            return ["Change shipping address", "Modify items", "Cancel order", "Upgrade shipping"]
        elif status == "shipped":
            return ["Change delivery address (if possible)", "Request delivery hold",
                    "Cancel order (restocking fee may apply)"]
        else:
            return ["Contact customer service"]

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create standardized error response."""
        return {
            "status": "error",
            "error": error_message,
            "user_message": "I encountered an issue while processing your request. Let me try a different approach.",
            "timestamp": datetime.now().isoformat()
        }


def test_mock_agents():
    """Test all mock agents with various scenarios."""
    print("🧪 Testing Mock Agent Manager with Discovery Agent")
    print("=" * 70)

    agent_manager = MockAgentManager()

    # Sample context
    sample_context = {
        "total_facts": 5,
        "facts_by_source": {
            "user": {"category": "electronics", "budget": "under $1500"},
            "nlu": {"subcategory": "laptop", "specifications": ["gaming"]}
        }
    }

    # Test 1: Discovery Agent - Specific user
    print("1️⃣ Testing DiscoveryAgent (Specific User):")
    discovery_result = agent_manager.call_agent("DiscoveryAgent",
                                                {"category": "electronics",
                                                 "subcategory": "laptop",
                                                 "specifications": {"graphics": "rtx", "ram": "16gb"},
                                                 "budget": "under $1500",
                                                 "user_message": "Show me gaming laptops with RTX graphics and 16GB RAM under $1500"},
                                                sample_context)
    print(f"   Status: {discovery_result['status']}")
    print(f"   Discovery Mode: {discovery_result['discovery_mode']}")
    print(f"   User Specificity: {discovery_result['user_specificity']}")
    print(f"   Products Found: {discovery_result.get('products_found', 0)}")

    # Test 2: Discovery Agent - Vague user
    print("\n2️⃣ Testing DiscoveryAgent (Vague User):")
    vague_result = agent_manager.call_agent("DiscoveryAgent",
                                            {"category": "electronics",
                                             "subcategory": "laptop",
                                             "specifications": {},
                                             "user_message": "I need a good laptop, can you recommend something?",
                                             "use_case": "general use"},
                                            sample_context)
    print(f"   Status: {vague_result['status']}")
    print(f"   Discovery Mode: {vague_result['discovery_mode']}")
    print(f"   User Specificity: {vague_result['user_specificity']}")
    print(f"   Recommendations: {len(vague_result.get('recommendations', []))}")

    # Test 3: Order Agent - with order ID
    print("\n3️⃣ Testing OrderAgent:")
    order_result = agent_manager.call_agent("OrderAgent",
                                            {"order_id": "12345", "action": "track"},
                                            sample_context)
    print(f"   Status: {order_result['status']}")
    print(f"   Order Status: {order_result.get('order_info', {}).get('status', 'N/A')}")

    # Test 4: Order Agent - without order ID (should show recent orders)
    print("\n4️⃣ Testing OrderAgent (No Order ID):")
    no_order_result = agent_manager.call_agent("OrderAgent",
                                               {"action": "track"},
                                               sample_context)
    print(f"   Status: {no_order_result['status']}")
    print(f"   Requires Selection: {no_order_result.get('requires_selection', False)}")
    print(f"   Recent Orders: {len(no_order_result.get('recent_orders', []))}")

    # Test 5: Return Agent - with order ID
    print("\n5️⃣ Testing ReturnAgent:")
    return_result = agent_manager.call_agent("ReturnAgent",
                                             {"order_id": "67890", "return_reason": "defective"},
                                             sample_context)
    print(f"   Status: {return_result['status']}")
    print(f"   Return Initiated: {return_result.get('return_initiated', False)}")

    # Test 6: Return Agent - without order ID (should show returnable orders)
    print("\n6️⃣ Testing ReturnAgent (No Order ID):")
    no_return_result = agent_manager.call_agent("ReturnAgent",
                                                {"return_reason": "not satisfied"},
                                                sample_context)
    print(f"   Status: {no_return_result['status']}")
    print(f"   Requires Selection: {no_return_result.get('requires_selection', False)}")
    print(f"   Returnable Orders: {len(no_return_result.get('returnable_orders', []))}")

    # Test 7: Error handling
    print("\n7️⃣ Testing error handling:")
    error_result = agent_manager.call_agent("InvalidAgent", {}, sample_context)
    print(f"   Error handled: {error_result['status'] == 'error'}")

    print("\n" + "=" * 70)
    print("✅ Mock Agent Tests Complete!")
    print("\nKey Features Demonstrated:")
    print("🔍 Dual-mode Discovery Agent (search-first vs recommend-first)")
    print("📦 Smart order lookup without requiring order ID")
    print("↩️ Intelligent return processing with order selection")
    print("🎯 Context-aware agent responses")


if __name__ == "__main__":
    test_mock_agents()