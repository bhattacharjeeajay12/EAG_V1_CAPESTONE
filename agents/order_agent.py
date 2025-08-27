# core_1/order_agent.py
"""
Order Agent - Comprehensive Order Management and Tracking

Purpose: Handles all order-related operations including tracking, modification,
cancellation, and customer service. Provides intelligent order lookup when
users don't remember order IDs and comprehensive order status information.

Key Features:
- Order tracking with detailed status updates
- Smart order lookup without requiring order ID
- Order modification and cancellation support
- Delivery management and address changes
- Integration with shipping carriers
- Customer service escalation
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import random


class OrderStatus(Enum):
    """Order status types."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class OrderAction(Enum):
    """Available order actions."""
    TRACK = "track"
    MODIFY = "modify"
    CANCEL = "cancel"
    UPDATE_ADDRESS = "update_address"
    CHANGE_DELIVERY = "change_delivery"
    CONTACT_SUPPORT = "contact_support"


@dataclass
class OrderItem:
    """Represents an item in an order."""
    name: str
    quantity: int
    price: float
    product_id: str
    status: str = "processing"
    tracking_info: Optional[Dict[str, Any]] = None


@dataclass
class OrderInfo:
    """Comprehensive order information."""
    order_id: str
    status: OrderStatus
    items: List[OrderItem]
    total_amount: float
    order_date: str
    estimated_delivery: Optional[str] = None
    actual_delivery: Optional[str] = None
    shipping_address: Dict[str, str] = None
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    customer_notes: List[str] = None
    modification_history: List[Dict[str, Any]] = None


@dataclass
class OrderActionResult:
    """Result of an order action."""
    success: bool
    action_performed: str
    order_info: OrderInfo
    message: str
    next_actions: List[str]
    requires_confirmation: bool = False
    confirmation_details: Optional[Dict[str, Any]] = None


class OrderAgent:
    """
    Comprehensive order management agent that handles tracking, modifications,
    and customer service for orders.
    """

    def __init__(self, order_database: List[Dict[str, Any]] = None):
        """Initialize Order Agent with order database."""
        self.order_database = order_database or []
        self.supported_carriers = ["FedEx", "UPS", "USPS", "DHL", "Amazon Logistics"]
        self.modification_policies = self._initialize_modification_policies()

    def process_order_request(self, request_params: Dict[str, Any],
                              context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main order processing method.

        Args:
            request_params: Order request parameters
            context: Current conversation context

        Returns:
            Comprehensive order processing result
        """
        try:
            # Extract request details
            order_id = request_params.get("order_id")
            action = request_params.get("action", OrderAction.TRACK.value)
            user_query = request_params.get("user_query", "")

            # Handle no order ID scenario
            if not order_id:
                return self._handle_missing_order_id(user_query, context)

            # Lookup order
            order_info = self._lookup_order(order_id)
            if not order_info:
                return self._handle_order_not_found(order_id, context)

            # Process specific action
            if action == OrderAction.TRACK.value:
                return self._track_order(order_info, request_params)
            elif action == OrderAction.MODIFY.value:
                return self._modify_order(order_info, request_params)
            elif action == OrderAction.CANCEL.value:
                return self._cancel_order(order_info, request_params)
            elif action == OrderAction.UPDATE_ADDRESS.value:
                return self._update_delivery_address(order_info, request_params)
            elif action == OrderAction.CHANGE_DELIVERY.value:
                return self._change_delivery_options(order_info, request_params)
            else:
                return self._handle_general_inquiry(order_info, user_query)

        except Exception as e:
            return self._create_error_response(f"Order processing error: {str(e)}")

    def _handle_missing_order_id(self, user_query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle requests without order ID by showing user's recent orders."""

        # Get user's recent orders (in real implementation, this would query by customer ID)
        recent_orders = self._get_user_recent_orders(context)

        if not recent_orders:
            return {
                "success": False,
                "status": "no_orders_found",
                "user_message": "I couldn't find any recent orders associated with your account. Could you provide your order ID?",
                "next_actions": ["provide_order_id", "check_email", "contact_support"],
                "order_lookup_performed": True
            }

        # Analyze query to filter relevant orders
        relevant_orders = self._filter_orders_by_query(recent_orders, user_query)

        if len(relevant_orders) == 1:
            # Single matching order - proceed directly
            order_info = self._lookup_order(relevant_orders[0]["order_id"])
            return self._track_order(order_info, {"detailed": True})

        else:
            # Multiple orders - show selection
            order_list = []
            for order in relevant_orders[:5]:  # Show top 5
                items_summary = self._create_items_summary(order["items"])
                order_list.append(
                    f"• Order {order['order_id']} - {items_summary} "
                    f"(${order['total_amount']}) - {order['status'].title()}"
                )

            return {
                "success": True,
                "status": "order_selection_required",
                "recent_orders": relevant_orders,
                "user_message": "Here are your recent orders. Which one are you asking about?\n\n" +
                                "\n".join(order_list) +
                                "\n\nPlease tell me the order number you're interested in.",
                "next_actions": ["select_order", "provide_order_id"],
                "order_lookup_performed": True,
                "requires_selection": True
            }

    def _track_order(self, order_info: OrderInfo, params: Dict[str, Any]) -> Dict[str, Any]:
        """Provide comprehensive order tracking information."""

        detailed = params.get("detailed", False)

        # Generate tracking message
        tracking_message = self._create_tracking_message(order_info, detailed)

        # Get available actions based on order status
        available_actions = self._get_available_actions(order_info)

        # Check for delivery issues or delays
        delivery_insights = self._analyze_delivery_status(order_info)

        result = {
            "success": True,
            "status": "tracking_provided",
            "order_info": self._order_to_dict(order_info),
            "tracking_details": {
                "current_status": order_info.status.value,
                "status_description": self._get_status_description(order_info.status),
                "estimated_delivery": order_info.estimated_delivery,
                "tracking_number": order_info.tracking_number,
                "carrier": order_info.carrier,
                "last_update": self._get_last_tracking_update(order_info)
            },
            "user_message": tracking_message,
            "next_actions": available_actions,
            "delivery_insights": delivery_insights,
            "order_lookup_performed": True
        }

        # Add shipping details if available
        if order_info.tracking_number and order_info.carrier:
            result["shipping_details"] = self._get_shipping_details(order_info)

        return result

    def _modify_order(self, order_info: OrderInfo, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle order modification requests."""

        modification_type = params.get("modification_type", "general")

        # Check if modification is allowed
        modification_check = self._check_modification_eligibility(order_info)

        if not modification_check["allowed"]:
            return {
                "success": False,
                "status": "modification_not_allowed",
                "order_info": self._order_to_dict(order_info),
                "user_message": f"Unfortunately, order {order_info.order_id} cannot be modified. {modification_check['reason']}",
                "alternatives": modification_check.get("alternatives", []),
                "next_actions": ["contact_support", "cancel_order"],
                "order_lookup_performed": True
            }

        # Get available modification options
        modification_options = self._get_modification_options(order_info)

        if modification_type == "general":
            # Show all available modifications
            options_text = "\n".join([f"• {opt['name']}: {opt['description']}"
                                      for opt in modification_options])

            return {
                "success": True,
                "status": "modification_options_provided",
                "order_info": self._order_to_dict(order_info),
                "modification_options": modification_options,
                "user_message": f"Here are the modification options available for order {order_info.order_id}:\n\n{options_text}\n\nWhat would you like to change?",
                "next_actions": ["select_modification", "cancel_modification"],
                "order_lookup_performed": True,
                "requires_confirmation": False
            }
        else:
            # Handle specific modification
            return self._process_specific_modification(order_info, modification_type, params)

    def _cancel_order(self, order_info: OrderInfo, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle order cancellation requests."""

        # Check cancellation eligibility
        cancellation_check = self._check_cancellation_eligibility(order_info)

        if not cancellation_check["allowed"]:
            return {
                "success": False,
                "status": "cancellation_not_allowed",
                "order_info": self._order_to_dict(order_info),
                "user_message": f"Unfortunately, order {order_info.order_id} cannot be cancelled. {cancellation_check['reason']}",
                "alternatives": cancellation_check.get("alternatives", ["contact_support", "return_after_delivery"]),
                "next_actions": ["contact_support", "process_return"],
                "order_lookup_performed": True
            }

        # Calculate cancellation details
        refund_amount = self._calculate_cancellation_refund(order_info)
        cancellation_fee = cancellation_check.get("fee", 0)

        confirmation_required = params.get("confirm", False)

        if not confirmation_required:
            # Request confirmation
            return {
                "success": True,
                "status": "cancellation_confirmation_required",
                "order_info": self._order_to_dict(order_info),
                "cancellation_details": {
                    "refund_amount": refund_amount,
                    "cancellation_fee": cancellation_fee,
                    "final_refund": refund_amount - cancellation_fee,
                    "refund_timeline": "3-5 business days"
                },
                "user_message": f"Are you sure you want to cancel order {order_info.order_id}?\n\n"
                                f"Refund amount: ${refund_amount}\n"
                                f"Cancellation fee: ${cancellation_fee}\n"
                                f"Final refund: ${refund_amount - cancellation_fee}\n\n"
                                f"Please confirm if you'd like to proceed with the cancellation.",
                "next_actions": ["confirm_cancellation", "keep_order"],
                "requires_confirmation": True,
                "order_lookup_performed": True
            }
        else:
            # Process cancellation
            cancellation_result = self._process_cancellation(order_info, params)

            return {
                "success": True,
                "status": "order_cancelled",
                "order_info": self._order_to_dict(order_info),
                "cancellation_result": cancellation_result,
                "user_message": f"Your order {order_info.order_id} has been successfully cancelled. "
                                f"You'll receive a refund of ${cancellation_result['refund_amount']} "
                                f"within {cancellation_result['refund_timeline']}.",
                "next_actions": ["track_refund", "place_new_order"],
                "order_lookup_performed": True
            }

    def _get_user_recent_orders(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get user's recent orders from database."""
        # In real implementation, would query by customer_id from context
        # For now, return sample orders
        return self.order_database[-10:] if self.order_database else []

    def _filter_orders_by_query(self, orders: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Filter orders based on user query context."""

        if not query:
            return orders

        query_lower = query.lower()
        filtered = []

        for order in orders:
            # Check if query matches order details
            items_text = " ".join([item.get("name", "") for item in order.get("items", [])]).lower()

            if any(keyword in query_lower for keyword in ["laptop", "phone", "headphones"]):
                if any(keyword in items_text for keyword in ["laptop", "phone", "headphones"]):
                    filtered.append(order)
            elif any(keyword in query_lower for keyword in ["recent", "latest", "last"]):
                filtered.append(order)  # Include recent orders
            else:
                filtered.append(order)  # Include all if no specific filter

        return filtered or orders  # Return all if no matches

    def _lookup_order(self, order_id: str) -> Optional[OrderInfo]:
        """Look up order by ID and convert to OrderInfo object."""

        for order_data in self.order_database:
            if order_data.get("order_id") == order_id:
                return self._dict_to_order_info(order_data)
        return None

    def _dict_to_order_info(self, order_dict: Dict[str, Any]) -> OrderInfo:
        """Convert dictionary to OrderInfo object."""

        items = [
            OrderItem(
                name=item.get("name", ""),
                quantity=item.get("quantity", 1),
                price=item.get("price", 0),
                product_id=item.get("product_id", ""),
                status=item.get("status", "processing")
            ) for item in order_dict.get("items", [])
        ]

        return OrderInfo(
            order_id=order_dict.get("order_id", ""),
            status=OrderStatus(order_dict.get("status", "processing")),
            items=items,
            total_amount=order_dict.get("total_amount", 0),
            order_date=order_dict.get("order_date", ""),
            estimated_delivery=order_dict.get("estimated_delivery"),
            actual_delivery=order_dict.get("actual_delivery"),
            tracking_number=order_dict.get("tracking_number"),
            carrier=order_dict.get("carrier"),
            customer_notes=order_dict.get("customer_notes", []),
            modification_history=order_dict.get("modification_history", [])
        )

    def _order_to_dict(self, order_info: OrderInfo) -> Dict[str, Any]:
        """Convert OrderInfo to dictionary."""

        return {
            "order_id": order_info.order_id,
            "status": order_info.status.value,
            "items": [
                {
                    "name": item.name,
                    "quantity": item.quantity,
                    "price": item.price,
                    "product_id": item.product_id,
                    "status": item.status
                } for item in order_info.items
            ],
            "total_amount": order_info.total_amount,
            "order_date": order_info.order_date,
            "estimated_delivery": order_info.estimated_delivery,
            "actual_delivery": order_info.actual_delivery,
            "tracking_number": order_info.tracking_number,
            "carrier": order_info.carrier
        }

    def _create_tracking_message(self, order_info: OrderInfo, detailed: bool = False) -> str:
        """Create user-friendly tracking message."""

        status_messages = {
            OrderStatus.PENDING: "Your order is being reviewed and will be confirmed shortly.",
            OrderStatus.CONFIRMED: "Your order has been confirmed and is being prepared.",
            OrderStatus.PROCESSING: "Your order is being processed and prepared for shipment.",
            OrderStatus.SHIPPED: "Great news! Your order has shipped and is on its way.",
            OrderStatus.OUT_FOR_DELIVERY: "Your order is out for delivery and should arrive today.",
            OrderStatus.DELIVERED: "Your order has been successfully delivered.",
            OrderStatus.CANCELLED: "This order has been cancelled.",
            OrderStatus.RETURNED: "This order has been returned."
        }

        base_message = f"Order {order_info.order_id}: {status_messages.get(order_info.status, 'Status unknown')}"

        # Add delivery information
        if order_info.estimated_delivery:
            if order_info.status in [OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.OUT_FOR_DELIVERY]:
                base_message += f"\nEstimated delivery: {order_info.estimated_delivery}"

        # Add tracking information
        if order_info.tracking_number and order_info.carrier:
            base_message += f"\nTracking: {order_info.tracking_number} via {order_info.carrier}"

        # Add detailed information if requested
        if detailed:
            items_summary = self._create_items_summary(order_info.items)
            base_message += f"\nItems: {items_summary}"
            base_message += f"\nTotal: ${order_info.total_amount}"

        return base_message

    def _create_items_summary(self, items: List) -> str:
        """Create a summary of order items."""
        if not items:
            return "No items"

        if len(items) == 1:
            item = items[0]
            name = item.get("name", item.name if hasattr(item, 'name') else "Unknown item")
            return name
        else:
            return f"{len(items)} items"

    def _get_available_actions(self, order_info: OrderInfo) -> List[str]:
        """Get available actions based on order status."""

        actions = ["get_details", "contact_support"]

        if order_info.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PROCESSING]:
            actions.extend(["modify_order", "cancel_order", "update_address"])
        elif order_info.status == OrderStatus.SHIPPED:
            actions.extend(["track_shipment", "update_delivery_preferences"])
        elif order_info.status == OrderStatus.DELIVERED:
            actions.extend(["return_items", "leave_review", "reorder"])

        return actions

    def _analyze_delivery_status(self, order_info: OrderInfo) -> Dict[str, Any]:
        """Analyze delivery status and provide insights."""

        insights = {"has_issues": False, "messages": []}

        if order_info.estimated_delivery:
            try:
                estimated_date = datetime.strptime(order_info.estimated_delivery, "%Y-%m-%d")
                today = datetime.now()

                if order_info.status != OrderStatus.DELIVERED and today > estimated_date:
                    insights["has_issues"] = True
                    insights["messages"].append("Your order appears to be delayed. We'll update you with new timing.")
                elif order_info.status == OrderStatus.SHIPPED:
                    days_to_delivery = (estimated_date - today).days
                    if days_to_delivery <= 1:
                        insights["messages"].append("Your order should arrive soon!")

            except ValueError:
                pass  # Invalid date format

        return insights

    def _check_modification_eligibility(self, order_info: OrderInfo) -> Dict[str, Any]:
        """Check if order can be modified."""

        if order_info.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.RETURNED]:
            return {
                "allowed": False,
                "reason": f"Orders that are {order_info.status.value} cannot be modified.",
                "alternatives": ["contact_support", "place_new_order"]
            }
        elif order_info.status == OrderStatus.SHIPPED:
            return {
                "allowed": False,
                "reason": "Orders that have shipped cannot be modified.",
                "alternatives": ["change_delivery_address", "contact_support"]
            }
        else:
            return {"allowed": True, "reason": "Order can be modified"}

    def _check_cancellation_eligibility(self, order_info: OrderInfo) -> Dict[str, Any]:
        """Check if order can be cancelled."""

        if order_info.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.RETURNED]:
            return {
                "allowed": False,
                "reason": f"Orders that are {order_info.status.value} cannot be cancelled.",
                "alternatives": ["process_return" if order_info.status == OrderStatus.DELIVERED else "contact_support"]
            }
        elif order_info.status == OrderStatus.SHIPPED:
            return {
                "allowed": True,
                "reason": "Shipped orders can be cancelled but may incur fees.",
                "fee": 25.0  # Restocking fee
            }
        else:
            return {"allowed": True, "reason": "Order can be cancelled", "fee": 0.0}

    def _get_modification_options(self, order_info: OrderInfo) -> List[Dict[str, Any]]:
        """Get available modification options for an order."""

        options = []

        if order_info.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PROCESSING]:
            options.extend([
                {"name": "change_items", "description": "Modify items in your order"},
                {"name": "update_address", "description": "Change delivery address"},
                {"name": "upgrade_shipping", "description": "Upgrade to faster shipping"},
                {"name": "add_notes", "description": "Add special delivery instructions"}
            ])
        elif order_info.status == OrderStatus.SHIPPED:
            options.extend([
                {"name": "update_address", "description": "Update delivery address (if possible)"},
                {"name": "delivery_preferences", "description": "Set delivery preferences"}
            ])

        return options

    def _process_specific_modification(self, order_info: OrderInfo, modification_type: str,
                                       params: Dict[str, Any]) -> Dict[str, Any]:
        """Process a specific modification request."""

        # Simulate modification processing
        modification_result = {
            "modification_id": f"MOD_{random.randint(100000, 999999)}",
            "type": modification_type,
            "status": "completed",
            "details": params
        }

        return {
            "success": True,
            "status": "modification_completed",
            "order_info": self._order_to_dict(order_info),
            "modification_result": modification_result,
            "user_message": f"Your order modification has been processed successfully. Modification ID: {modification_result['modification_id']}",
            "next_actions": ["track_order", "contact_support"],
            "order_lookup_performed": True
        }

    def _calculate_cancellation_refund(self, order_info: OrderInfo) -> float:
        """Calculate refund amount for order cancellation."""
        return order_info.total_amount  # Full refund in most cases

    def _process_cancellation(self, order_info: OrderInfo, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process order cancellation."""

        refund_amount = self._calculate_cancellation_refund(order_info)
        cancellation_fee = params.get("cancellation_fee", 0)

        return {
            "cancellation_id": f"CAN_{random.randint(100000, 999999)}",
            "refund_amount": refund_amount - cancellation_fee,
            "cancellation_fee": cancellation_fee,
            "refund_timeline": "3-5 business days",
            "refund_method": "Original payment method",
            "status": "processed"
        }

    def _get_shipping_details(self, order_info: OrderInfo) -> Dict[str, Any]:
        """Get detailed shipping information."""

        return {
            "carrier": order_info.carrier,
            "tracking_number": order_info.tracking_number,
            "service_type": "Standard Shipping",
            "tracking_url": f"https://{order_info.carrier.lower().replace(' ', '')}.com/track/{order_info.tracking_number}",
            "estimated_delivery": order_info.estimated_delivery
        }

    def _get_status_description(self, status: OrderStatus) -> str:
        """Get detailed description of order status."""

        descriptions = {
            OrderStatus.PENDING: "Order received and awaiting confirmation",
            OrderStatus.CONFIRMED: "Order confirmed and queued for processing",
            OrderStatus.PROCESSING: "Items being prepared and packaged",
            OrderStatus.SHIPPED: "Package has left our facility and is in transit",
            OrderStatus.OUT_FOR_DELIVERY: "Package is with delivery carrier for final delivery",
            OrderStatus.DELIVERED: "Package has been successfully delivered",
            OrderStatus.CANCELLED: "Order has been cancelled",
            OrderStatus.RETURNED: "Order has been returned"
        }

        return descriptions.get(status, "Status unknown")

    def _get_last_tracking_update(self, order_info: OrderInfo) -> str:
        """Get last tracking update timestamp."""
        # Simulate last update time
        return (datetime.now() - timedelta(hours=random.randint(1, 12))).strftime("%Y-%m-%d %H:%M")

    def _handle_order_not_found(self, order_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle case when order is not found."""

        return {
            "success": False,
            "status": "order_not_found",
            "user_message": f"I couldn't find order {order_id}. Please check the order number and try again, or let me show you your recent orders.",
            "suggestions": [
                "Double-check the order number",
                "Check your email confirmation",
                "Look for order in your account",
                "Contact customer support"
            ],
            "next_actions": ["show_recent_orders", "provide_correct_id", "contact_support"],
            "order_lookup_performed": True
        }

    def _handle_general_inquiry(self, order_info: OrderInfo, query: str) -> Dict[str, Any]:
        """Handle general order inquiries."""

        return {
            "success": True,
            "status": "general_inquiry_handled",
            "order_info": self._order_to_dict(order_info),
            "user_message": f"I found your order {order_info.order_id}. How can I help you with this order?",
            "next_actions": self._get_available_actions(order_info),
            "order_lookup_performed": True
        }

    def _initialize_modification_policies(self) -> Dict[str, Any]:
        """Initialize order modification policies."""

        return {
            "address_change_cutoff": "shipped",
            "item_modification_cutoff": "processing",
            "cancellation_fee_threshold": "shipped",
            "modification_time_limit": 24  # hours
        }

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create standardized error response."""

        return {
            "success": False,
            "status": "error",
            "error": error_message,
            "user_message": "I encountered an issue while processing your order request. Please try again or contact customer support.",
            "next_actions": ["try_again", "contact_support"],
            "order_lookup_performed": False
        }


def test_order_agent():
    """Test Order Agent with various scenarios."""
    print("🧪 Testing Order Agent")
    print("=" * 60)

    # Sample order database
    sample_orders = [
        {
            "order_id": "12345",
            "status": "shipped",
            "items": [{"name": "Dell Gaming Laptop G15", "quantity": 1, "price": 1299, "product_id": "laptop_001"}],
            "total_amount": 1299,
            "order_date": "2024-12-20",
            "estimated_delivery": "2024-12-28",
            "tracking_number": "TRK123456789",
            "carrier": "FedEx"
        },
        {
            "order_id": "67890",
            "status": "delivered",
            "items": [{"name": "iPhone 15 Pro", "quantity": 1, "price": 999, "product_id": "phone_001"}],
            "total_amount": 999,
            "order_date": "2024-12-15",
            "estimated_delivery": "2024-12-22",
            "actual_delivery": "2024-12-22"
        },
        {
            "order_id": "URGENT123",
            "status": "processing",
            "items": [{"name": "Sony Headphones", "quantity": 1, "price": 399, "product_id": "headphones_001"}],
            "total_amount": 399,
            "order_date": "2024-12-25",
            "estimated_delivery": "2024-12-30"
        }
    ]

    order_agent = OrderAgent(sample_orders)
    sample_context = {"user_id": "user123"}

    # Test 1: Track order with order ID
    print("1️⃣ Track order with order ID:")
    result1 = order_agent.process_order_request(
        {"order_id": "12345", "action": "track"},
        sample_context
    )
    print(f"   Success: {result1['success']}")
    print(f"   Status: {result1['status']}")
    print(f"   Order Status: {result1.get('tracking_details', {}).get('current_status', 'N/A')}")

    # Test 2: Track order without order ID (should show recent orders)
    print("\n2️⃣ Track order without order ID:")
    result2 = order_agent.process_order_request(
        {"action": "track", "user_query": "where is my laptop order"},
        sample_context
    )
    print(f"   Success: {result2['success']}")
    print(f"   Status: {result2['status']}")
    print(f"   Requires Selection: {result2.get('requires_selection', False)}")
    print(f"   Recent Orders Found: {len(result2.get('recent_orders', []))}")

    # Test 3: Modify order
    print("\n3️⃣ Modify order:")
    result3 = order_agent.process_order_request(
        {"order_id": "URGENT123", "action": "modify"},
        sample_context
    )
    print(f"   Success: {result3['success']}")
    print(f"   Status: {result3['status']}")
    print(f"   Modification Options: {len(result3.get('modification_options', []))}")

    # Test 4: Cancel order
    print("\n4️⃣ Cancel order (request confirmation):")
    result4 = order_agent.process_order_request(
        {"order_id": "URGENT123", "action": "cancel"},
        sample_context
    )
    print(f"   Success: {result4['success']}")
    print(f"   Status: {result4['status']}")
    print(f"   Requires Confirmation: {result4.get('requires_confirmation', False)}")
    if result4.get('cancellation_details'):
        print(f"   Refund Amount: ${result4['cancellation_details']['refund_amount']}")

    # Test 5: Order not found
    print("\n5️⃣ Order not found:")
    result5 = order_agent.process_order_request(
        {"order_id": "NOTFOUND", "action": "track"},
        sample_context
    )
    print(f"   Success: {result5['success']}")
    print(f"   Status: {result5['status']}")
    print(f"   Suggestions: {len(result5.get('suggestions', []))}")

    print("\n" + "=" * 60)
    print("✅ Order Agent Tests Complete!")


if __name__ == "__main__":
    test_order_agent()