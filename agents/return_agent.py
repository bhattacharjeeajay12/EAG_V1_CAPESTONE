# core/return_agent.py
"""
Return Agent - Comprehensive Return and Refund Management

Purpose: Handles all return-related operations including return initiation,
eligibility checking, return processing, refund management, and exchange
handling. Provides intelligent order lookup when users don't remember order IDs.

Key Features:
- Smart return eligibility checking
- Return reason analysis and validation
- Multiple return types (refund, exchange, store credit)
- Automatic return label generation
- Return tracking and status updates
- Integration with order management system
- Customer service escalation
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import random


class ReturnReason(Enum):
    """Return reason categories."""
    DEFECTIVE = "defective"
    WRONG_ITEM = "wrong_item"
    DAMAGED_SHIPPING = "damaged_shipping"
    NOT_AS_DESCRIBED = "not_as_described"
    CHANGED_MIND = "changed_mind"
    SIZE_ISSUE = "size_issue"
    QUALITY_ISSUE = "quality_issue"
    LATE_DELIVERY = "late_delivery"
    OTHER = "other"


class ReturnType(Enum):
    """Types of returns."""
    REFUND = "refund"
    EXCHANGE = "exchange"
    STORE_CREDIT = "store_credit"
    REPAIR = "repair"


class ReturnStatus(Enum):
    """Return processing status."""
    INITIATED = "initiated"
    APPROVED = "approved"
    LABEL_SENT = "label_sent"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"


@dataclass
class ReturnItem:
    """Item being returned."""
    product_id: str
    name: str
    quantity: int
    original_price: float
    return_reason: ReturnReason
    condition: str = "good"
    photos_provided: bool = False


@dataclass
class ReturnRequest:
    """Complete return request information."""
    return_id: str
    order_id: str
    items: List[ReturnItem]
    return_type: ReturnType
    total_refund_amount: float
    return_reason: ReturnReason
    customer_notes: str = ""
    status: ReturnStatus = ReturnStatus.INITIATED
    created_at: str = None
    estimated_processing_time: str = "5-7 business days"


@dataclass
class ReturnEligibility:
    """Return eligibility assessment."""
    eligible: bool
    reason: str
    conditions: List[str]
    time_remaining: Optional[str] = None
    alternatives: List[str] = None


class ReturnAgent:
    """
    Comprehensive return management agent that handles return initiation,
    processing, tracking, and customer service.
    """

    def __init__(self, order_database: List[Dict[str, Any]] = None):
        """Initialize Return Agent with order database."""
        self.order_database = order_database or []
        self.return_policies = self._initialize_return_policies()
        self.return_database = []  # Track processed returns

    def process_return_request(self, request_params: Dict[str, Any],
                               context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main return processing method.

        Args:
            request_params: Return request parameters
            context: Current conversation context

        Returns:
            Comprehensive return processing result
        """
        try:
            # Extract request details
            order_id = request_params.get("order_id")
            return_reason = request_params.get("return_reason", "not_specified")
            items_to_return = request_params.get("items", [])
            return_type = request_params.get("return_type", ReturnType.REFUND.value)

            # Handle no order ID scenario
            if not order_id:
                return self._handle_missing_order_id(request_params.get("user_query", ""), context)

            # Lookup and validate order
            order_info = self._lookup_order(order_id)
            if not order_info:
                return self._handle_order_not_found(order_id)

            # Check return eligibility
            eligibility = self._check_return_eligibility(order_info)
            if not eligibility.eligible:
                return self._handle_ineligible_return(order_info, eligibility)

            # Process return based on current state
            existing_return = self._find_existing_return(order_id)
            if existing_return:
                return self._handle_existing_return(existing_return, request_params)

            # Create new return request
            return self._create_return_request(order_info, return_reason, items_to_return, return_type)

        except Exception as e:
            return self._create_error_response(f"Return processing error: {str(e)}")

    def _handle_missing_order_id(self, user_query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle return requests without order ID by showing returnable orders."""

        # Get user's returnable orders
        returnable_orders = self._get_returnable_orders(context)

        if not returnable_orders:
            return {
                "success": False,
                "status": "no_returnable_orders",
                "user_message": "I couldn't find any recent orders that are eligible for return. Returns must be initiated within our return window. Would you like me to check a specific order?",
                "next_actions": ["provide_order_id", "check_return_policy", "contact_support"],
                "return_lookup_performed": True
            }

        # Filter orders based on user query if provided
        relevant_orders = self._filter_returnable_orders(returnable_orders, user_query)

        if len(relevant_orders) == 1:
            # Single matching order - show return options
            order = relevant_orders[0]
            return self._show_return_options_for_order(order)

        else:
            # Multiple orders - show selection
            order_list = []
            for order in relevant_orders[:5]:  # Show top 5
                items_summary = self._create_items_summary(order["items"])
                days_since_delivery = self._calculate_days_since_delivery(order)
                order_list.append(
                    f"• Order {order['order_id']} - {items_summary} "
                    f"(Delivered {days_since_delivery} days ago)"
                )

            return {
                "success": True,
                "status": "order_selection_required",
                "returnable_orders": relevant_orders,
                "user_message": "Here are your recent orders that can be returned:\n\n" +
                                "\n".join(order_list) +
                                "\n\nWhich order would you like to return?",
                "next_actions": ["select_order", "provide_order_id"],
                "return_lookup_performed": True,
                "requires_selection": True
            }

    def _show_return_options_for_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Show return options for a specific order."""

        eligibility = self._check_return_eligibility(order)
        items_summary = self._create_items_summary(order["items"])

        return {
            "success": True,
            "status": "return_options_available",
            "order_info": order,
            "eligibility": eligibility.__dict__,
            "user_message": f"I can help you return order {order['order_id']} ({items_summary}). "
                            f"What's the reason for the return?\n\n"
                            f"Common reasons:\n"
                            f"• Item is defective or damaged\n"
                            f"• Wrong item received\n"
                            f"• Item not as described\n"
                            f"• Changed my mind\n"
                            f"• Size/fit issue\n"
                            f"• Other reason",
            "return_reasons": [reason.value for reason in ReturnReason],
            "next_actions": ["specify_return_reason", "select_items"],
            "return_lookup_performed": True
        }

    def _create_return_request(self, order_info: Dict[str, Any], return_reason: str,
                               items_to_return: List[str], return_type: str) -> Dict[str, Any]:
        """Create a new return request."""

        # Generate return ID
        return_id = f"RET{random.randint(100000, 999999)}"

        # Process return items
        return_items = self._process_return_items(order_info["items"], items_to_return, return_reason)

        # Calculate refund amount
        refund_calculation = self._calculate_refund_amount(return_items, return_type)

        # Create return request
        return_request = ReturnRequest(
            return_id=return_id,
            order_id=order_info["order_id"],
            items=return_items,
            return_type=ReturnType(return_type),
            total_refund_amount=refund_calculation["total_refund"],
            return_reason=ReturnReason(return_reason) if return_reason != "not_specified" else ReturnReason.OTHER,
            created_at=datetime.now().isoformat()
        )

        # Store return request
        self.return_database.append(return_request)

        # Generate return label and instructions
        return_label = self._generate_return_label(return_request, order_info)

        # Create comprehensive response
        return {
            "success": True,
            "status": "return_initiated",
            "return_info": {
                "return_id": return_id,
                "order_id": order_info["order_id"],
                "items_returned": [item.name for item in return_items],
                "return_reason": return_reason,
                "return_type": return_type,
                "refund_amount": refund_calculation["total_refund"],
                "processing_fee": refund_calculation.get("processing_fee", 0),
                "estimated_processing_time": return_request.estimated_processing_time
            },
            "return_label": return_label,
            "refund_breakdown": refund_calculation,
            "user_message": self._create_return_confirmation_message(return_request, refund_calculation, return_label),
            "next_steps": [
                "Package items securely",
                "Print return label",
                "Drop off at shipping location",
                "Track return progress"
            ],
            "next_actions": ["track_return", "modify_return", "contact_support"],
            "return_initiated": True
        }

    def _check_return_eligibility(self, order_info: Dict[str, Any]) -> ReturnEligibility:
        """Check if order is eligible for return."""

        order_status = order_info.get("status", "")
        order_date = order_info.get("order_date", "")
        delivery_date = order_info.get("delivery_date") or order_info.get("actual_delivery")

        # Order must be delivered to be returned
        if order_status != "delivered":
            if order_status in ["processing", "shipped"]:
                return ReturnEligibility(
                    eligible=True,
                    reason="Order can be cancelled before delivery",
                    conditions=["Cancellation may incur fees if already shipped"],
                    alternatives=["cancel_order"]
                )
            else:
                return ReturnEligibility(
                    eligible=False,
                    reason=f"Orders with status '{order_status}' cannot be returned",
                    conditions=[],
                    alternatives=["contact_support"]
                )

        # Check return window
        if delivery_date:
            try:
                delivered = datetime.strptime(delivery_date, "%Y-%m-%d")
                days_since_delivery = (datetime.now() - delivered).days
                return_window = self.return_policies["return_window_days"]

                if days_since_delivery <= return_window:
                    remaining_days = return_window - days_since_delivery
                    return ReturnEligibility(
                        eligible=True,
                        reason=f"Within return window ({remaining_days} days remaining)",
                        conditions=[
                            "Items must be in original condition",
                            "Original packaging preferred",
                            "Return shipping label will be provided"
                        ],
                        time_remaining=f"{remaining_days} days"
                    )
                else:
                    return ReturnEligibility(
                        eligible=False,
                        reason=f"Return window expired ({days_since_delivery} days since delivery)",
                        conditions=[],
                        alternatives=["contact_support", "check_warranty"]
                    )

            except ValueError:
                # Invalid date format
                pass

        # Fallback - assume eligible with conditions
        return ReturnEligibility(
            eligible=True,
            reason="Eligibility needs verification",
            conditions=["Return eligibility will be verified during processing"],
            alternatives=[]
        )

    def _get_returnable_orders(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get user's orders that are eligible for return."""

        returnable = []
        for order in self.order_database:
            eligibility = self._check_return_eligibility(order)
            if eligibility.eligible:
                returnable.append(order)

        # Sort by delivery date (most recent first)
        returnable.sort(key=lambda x: x.get("delivery_date", x.get("order_date", "")), reverse=True)
        return returnable

    def _filter_returnable_orders(self, orders: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Filter returnable orders based on user query."""

        if not query:
            return orders

        query_lower = query.lower()
        filtered = []

        for order in orders:
            # Check if query matches product names
            items_text = " ".join([item.get("name", "") for item in order.get("items", [])]).lower()

            if any(keyword in query_lower for keyword in ["laptop", "phone", "headphones", "tablet"]):
                if any(keyword in items_text for keyword in ["laptop", "phone", "headphones", "tablet"]):
                    filtered.append(order)
            elif any(keyword in query_lower for keyword in ["recent", "latest", "last"]):
                filtered.append(order)  # Include recent orders
            else:
                filtered.append(order)  # Include all if no specific filter

        return filtered or orders

    def _process_return_items(self, order_items: List[Dict[str, Any]],
                              items_to_return: List[str], return_reason: str) -> List[ReturnItem]:
        """Process items to be returned."""

        return_items = []

        if not items_to_return:
            # Return all items if none specified
            items_to_return = ["all"]

        for order_item in order_items:
            if "all" in items_to_return or order_item.get("name", "") in items_to_return:
                return_item = ReturnItem(
                    product_id=order_item.get("product_id", ""),
                    name=order_item.get("name", ""),
                    quantity=order_item.get("quantity", 1),
                    original_price=order_item.get("price", 0),
                    return_reason=ReturnReason(
                        return_reason) if return_reason != "not_specified" else ReturnReason.OTHER
                )
                return_items.append(return_item)

        return return_items

    def _calculate_refund_amount(self, return_items: List[ReturnItem], return_type: str) -> Dict[str, Any]:
        """Calculate refund amount and breakdown."""

        subtotal = sum(item.original_price * item.quantity for item in return_items)

        # Calculate fees and adjustments
        processing_fee = 0
        restocking_fee = 0

        # Apply processing fee for certain return reasons
        if any(item.return_reason == ReturnReason.CHANGED_MIND for item in return_items):
            processing_fee = min(subtotal * 0.1, 25.0)  # 10% up to $25

        # Apply restocking fee for opened electronics
        electronic_items = [item for item in return_items if
                            "laptop" in item.name.lower() or "phone" in item.name.lower()]
        if electronic_items:
            restocking_fee = min(sum(item.original_price * 0.05 for item in electronic_items), 50.0)

        # Calculate final refund
        total_refund = subtotal - processing_fee - restocking_fee

        return {
            "subtotal": subtotal,
            "processing_fee": processing_fee,
            "restocking_fee": restocking_fee,
            "total_refund": max(0, total_refund),
            "refund_method": "Original payment method",
            "estimated_timeline": "5-7 business days after we receive your return"
        }

    def _generate_return_label(self, return_request: ReturnRequest, order_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate return shipping label and instructions."""

        return {
            "label_generated": True,
            "tracking_number": f"RTN{random.randint(1000000000, 9999999999)}",
            "carrier": "UPS",
            "return_address": {
                "name": "Returns Processing Center",
                "address": "123 Return Lane",
                "city": "Processing City",
                "state": "PC",
                "zip": "12345"
            },
            "label_url": f"https://returns.example.com/label/{return_request.return_id}",
            "instructions": [
                "Package all items securely in original packaging if available",
                "Include all accessories and documentation",
                "Print and attach the return label",
                "Drop off at any UPS location or schedule pickup"
            ],
            "estimated_transit_time": "2-3 business days"
        }

    def _create_return_confirmation_message(self, return_request: ReturnRequest,
                                            refund_calculation: Dict[str, Any],
                                            return_label: Dict[str, Any]) -> str:
        """Create user-friendly return confirmation message."""

        items_list = ", ".join([item.name for item in return_request.items])

        message = f"✅ Return Request Confirmed!\n\n"
        message += f"Return ID: {return_request.return_id}\n"
        message += f"Order: {return_request.order_id}\n"
        message += f"Items: {items_list}\n\n"

        # Refund information
        message += f"💰 Refund Information:\n"
        if refund_calculation.get("processing_fee", 0) > 0:
            message += f"Subtotal: ${refund_calculation['subtotal']:.2f}\n"
            message += f"Processing fee: -${refund_calculation['processing_fee']:.2f}\n"
            message += f"Final refund: ${refund_calculation['total_refund']:.2f}\n"
        else:
            message += f"Refund amount: ${refund_calculation['total_refund']:.2f}\n"

        message += f"Refund timeline: {refund_calculation['estimated_timeline']}\n\n"

        # Return instructions
        message += f"📦 Next Steps:\n"
        message += f"1. A return label has been sent to your email\n"
        message += f"2. Package the items securely\n"
        message += f"3. Attach the return label\n"
        message += f"4. Drop off at any {return_label['carrier']} location\n\n"

        message += f"Track your return: RTN-{return_request.return_id}"

        return message

    def _handle_ineligible_return(self, order_info: Dict[str, Any],
                                  eligibility: ReturnEligibility) -> Dict[str, Any]:
        """Handle cases where return is not eligible."""

        return {
            "success": False,
            "status": "return_not_eligible",
            "order_info": order_info,
            "eligibility_info": eligibility.__dict__,
            "user_message": f"Unfortunately, order {order_info['order_id']} is not eligible for return. {eligibility.reason}",
            "alternatives": eligibility.alternatives or ["contact_support"],
            "next_actions": eligibility.alternatives or ["contact_support", "check_warranty"],
            "return_initiated": False
        }

    def _handle_existing_return(self, existing_return: ReturnRequest,
                                request_params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle case where return already exists for this order."""

        return {
            "success": True,
            "status": "existing_return_found",
            "return_info": {
                "return_id": existing_return.return_id,
                "status": existing_return.status.value,
                "items_returned": [item.name for item in existing_return.items],
                "refund_amount": existing_return.total_refund_amount
            },
            "user_message": f"I found an existing return request (ID: {existing_return.return_id}) for this order. "
                            f"Status: {existing_return.status.value}. Would you like to check the status or modify this return?",
            "next_actions": ["check_return_status", "modify_return", "create_new_return"],
            "return_initiated": False
        }

    def _find_existing_return(self, order_id: str) -> Optional[ReturnRequest]:
        """Find existing return for an order."""

        for return_req in self.return_database:
            if return_req.order_id == order_id and return_req.status not in [ReturnStatus.COMPLETED,
                                                                             ReturnStatus.REJECTED]:
                return return_req
        return None

    def _lookup_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Look up order by ID."""

        for order in self.order_database:
            if order.get("order_id") == order_id:
                return order
        return None

    def _handle_order_not_found(self, order_id: str) -> Dict[str, Any]:
        """Handle case when order is not found."""

        return {
            "success": False,
            "status": "order_not_found",
            "user_message": f"I couldn't find order {order_id}. Please check the order number, or let me show you your recent orders that can be returned.",
            "suggestions": [
                "Double-check the order number",
                "Check your email confirmation",
                "Look for the order in your account"
            ],
            "next_actions": ["show_returnable_orders", "provide_correct_id", "contact_support"],
            "return_lookup_performed": True
        }

    def _create_items_summary(self, items: List[Dict[str, Any]]) -> str:
        """Create a summary of order items."""

        if not items:
            return "No items"
        if len(items) == 1:
            return items[0].get("name", "Unknown item")
        else:
            return f"{len(items)} items including {items[0].get('name', 'Unknown item')}"

    def _calculate_days_since_delivery(self, order: Dict[str, Any]) -> int:
        """Calculate days since delivery."""

        delivery_date = order.get("delivery_date") or order.get("actual_delivery")
        if delivery_date:
            try:
                delivered = datetime.strptime(delivery_date, "%Y-%m-%d")
                return (datetime.now() - delivered).days
            except ValueError:
                pass
        return 0

    def _initialize_return_policies(self) -> Dict[str, Any]:
        """Initialize return policies and rules."""

        return {
            "return_window_days": 30,
            "processing_time_days": 7,
            "refund_timeline_days": 7,
            "restocking_fee_categories": ["electronics"],
            "no_return_categories": ["software", "digital"],
            "free_return_reasons": ["defective", "wrong_item", "damaged_shipping"],
            "fee_return_reasons": ["changed_mind", "size_issue"]
        }

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create standardized error response."""

        return {
            "success": False,
            "status": "error",
            "error": error_message,
            "user_message": "I encountered an issue while processing your return request. Please try again or contact customer support.",
            "next_actions": ["try_again", "contact_support"],
            "return_lookup_performed": False
        }


def test_return_agent():
    """Test Return Agent with various scenarios."""
    print("🧪 Testing Return Agent")
    print("=" * 60)

    # Sample order database
    sample_orders = [
        {
            "order_id": "12345",
            "status": "delivered",
            "items": [{"name": "Dell Gaming Laptop G15", "quantity": 1, "price": 1299, "product_id": "laptop_001"}],
            "total_amount": 1299,
            "order_date": "2024-12-15",
            "delivery_date": "2024-12-22"
        },
        {
            "order_id": "67890",
            "status": "delivered",
            "items": [{"name": "iPhone 15 Pro", "quantity": 1, "price": 999, "product_id": "phone_001"}],
            "total_amount": 999,
            "order_date": "2024-12-10",
            "delivery_date": "2024-12-18"
        },
        {
            "order_id": "OLD123",
            "status": "delivered",
            "items": [{"name": "Old Product", "quantity": 1, "price": 500, "product_id": "old_001"}],
            "total_amount": 500,
            "order_date": "2024-10-15",
            "delivery_date": "2024-10-22"  # Too old for return
        }
    ]

    return_agent = ReturnAgent(sample_orders)
    sample_context = {"user_id": "user123"}

    # Test 1: Return with order ID
    print("1️⃣ Return with order ID:")
    result1 = return_agent.process_return_request(
        {"order_id": "12345", "return_reason": "defective"},
        sample_context
    )
    print(f"   Success: {result1['success']}")
    print(f"   Status: {result1['status']}")
    if result1.get('return_info'):
        print(f"   Return ID: {result1['return_info']['return_id']}")
        print(f"   Refund Amount: ${result1['return_info']['refund_amount']}")

    # Test 2: Return without order ID (should show returnable orders)
    print("\n2️⃣ Return without order ID:")
    result2 = return_agent.process_return_request(
        {"user_query": "I want to return my laptop"},
        sample_context
    )
    print(f"   Success: {result2['success']}")
    print(f"   Status: {result2['status']}")
    print(f"   Requires Selection: {result2.get('requires_selection', False)}")
    print(f"   Returnable Orders Found: {len(result2.get('returnable_orders', []))}")

    # Test 3: Return with expired window
    print("\n3️⃣ Return with expired window:")
    result3 = return_agent.process_return_request(
        {"order_id": "OLD123", "return_reason": "changed_mind"},
        sample_context
    )
    print(f"   Success: {result3['success']}")
    print(f"   Status: {result3['status']}")
    if result3.get('eligibility_info'):
        print(f"   Eligible: {result3['eligibility_info']['eligible']}")
        print(f"   Reason: {result3['eligibility_info']['reason']}")

    # Test 4: Return with processing fee
    print("\n4️⃣ Return with processing fee (changed mind):")
    result4 = return_agent.process_return_request(
        {"order_id": "67890", "return_reason": "changed_mind"},
        sample_context
    )
    print(f"   Success: {result4['success']}")
    if result4.get('refund_breakdown'):
        breakdown = result4['refund_breakdown']
        print(f"   Subtotal: ${breakdown['subtotal']}")
        print(f"   Processing Fee: ${breakdown.get('processing_fee', 0)}")
        print(f"   Final Refund: ${breakdown['total_refund']}")

    # Test 5: Order not found
    print("\n5️⃣ Order not found:")
    result5 = return_agent.process_return_request(
        {"order_id": "NOTFOUND", "return_reason": "defective"},
        sample_context
    )
    print(f"   Success: {result5['success']}")
    print(f"   Status: {result5['status']}")
    print(f"   Suggestions: {len(result5.get('suggestions', []))}")

    print("\n" + "=" * 60)
    print("✅ Return Agent Tests Complete!")


if __name__ == "__main__":
    test_return_agent()