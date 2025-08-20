import os, json, uuid
from pydantic import BaseModel, Field
from typing import Dict, Optional, List, Union, Any
from datetime import datetime

# Try importing Gemini, but provide fallback if not available
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("[WARN] google.generativeai package not available. Using mock extraction.")

# Define schema for structured extraction
class OrderDetails(BaseModel):
    product_id: str
    product_name: Optional[str] = None
    quantity: int = 1
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    customer_id: Optional[str] = None
    payment_method: Optional[str] = "credit_card"
    shipping_address: Optional[Dict[str, str]] = None
    billing_address: Optional[Dict[str, str]] = None
    special_instructions: Optional[str] = None
    order_status: str = "pending"  # pending, processing, paid, shipped, delivered, failed, cancelled
    payment_status: str = "pending"  # pending, authorized, paid, failed, refunded
    payment_id: Optional[str] = None
    order_id: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_id": "123456",
                "product_name": "Wireless Headphones",
                "quantity": 1,
                "unit_price": 99.99,
                "total_price": 99.99,
                "customer_id": "cust_12345",
                "payment_method": "credit_card",
                "shipping_address": {
                    "street": "123 Main St",
                    "city": "Anytown",
                    "state": "CA",
                    "zip": "12345",
                    "country": "USA"
                },
                "order_status": "pending",
                "payment_status": "pending"
            }
        }
    }

def extract_order_details(input_data: Union[str, Dict]) -> OrderDetails:
    """
    Extracts order details from input data which can be either a JSON string or a dictionary.
    This is primarily used to convert data from the buy agent into a structured OrderDetails object.
    """
    try:
        if isinstance(input_data, str):
            # Try to parse as JSON if it's a string
            try:
                data = json.loads(input_data)
            except json.JSONDecodeError:
                # If it's not valid JSON, it might be a natural language query
                # which we'll handle with a fallback
                return _fallback_extract(input_data)
        else:
            data = input_data

        # Create OrderDetails from the parsed data
        return OrderDetails(**data)
    except Exception as e:
        print(f"[ERROR] Failed to extract order details: {e}")
        if isinstance(input_data, str):
            return _fallback_extract(input_data)
        else:
            # If input was already a dict but failed to parse, create a minimal valid order
            return OrderDetails(
                product_id=str(data.get("product_id", "unknown")),
                quantity=int(data.get("quantity", 1))
            )

def _fallback_extract(query: str) -> OrderDetails:
    """Simple fallback extraction when data cannot be parsed normally."""
    # Create a minimal valid order with default values
    return OrderDetails(
        product_id="unknown",
        quantity=1,
        order_status="pending",
        payment_status="pending"
    )

def process_payment(order_details: OrderDetails) -> Dict[str, Any]:
    """
    Simulates processing a payment through a payment gateway.
    In a real system, this would connect to an actual payment processor.
    """
    # This is a mock implementation
    # In a real system, you would call an actual payment gateway API

    # Generate a unique payment ID
    payment_id = f"pmt_{uuid.uuid4().hex[:8]}"

    # Simulate success/failure (80% success rate)
    import random
    success = random.random() < 0.8

    if success:
        result = {
            "payment_id": payment_id,
            "status": "paid",
            "message": "Payment processed successfully",
            "transaction_id": f"tx_{uuid.uuid4().hex[:10]}",
            "amount": order_details.total_price,
            "timestamp": datetime.now().isoformat()
        }
    else:
        result = {
            "payment_id": payment_id,
            "status": "failed",
            "message": random.choice([
                "Insufficient funds",
                "Card expired",
                "Card declined",
                "Payment gateway error"
            ]),
            "timestamp": datetime.now().isoformat()
        }

    return result

def generate_order_id() -> str:
    """Generate a unique order ID."""
    timestamp = datetime.now().strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:6].upper()
    return f"ORD-{timestamp}-{random_part}"
