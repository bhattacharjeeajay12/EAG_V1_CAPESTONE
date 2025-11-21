from enum import Enum

class WorkstreamState(str, Enum):
    NEW = "NEW"
    COLLECTING = "COLLECTING"
    READY = "READY"
    PROCESSING = "PROCESSING"
    PRESENTING = "PRESENTING"
    AWAITING_DECISION = "AWAITING_DECISION"
    CONFIRMING = "CONFIRMING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"

class Agents(str, Enum):
    DISCOVERY = "DISCOVERY"
    ORDER = "ORDER"
    PAYMENT = "PAYMENT"
    EXCHANGE = "EXCHANGE"
    RETURN = "RETURN"
    PLANNER = "PLANNER"

class WorkflowContinuityDecision(str, Enum):
    SWITCH = "SWITCH"
    CONTINUATION = "CONTINUATION"
    UNCLEAR = "UNCLEAR"

class Categories(str, Enum):
    ELECTRONICS = "electronics"
    SPORTS = "sports"

class MsgTypes(str, Enum):
    user = "user_message"
    ai_message = "ai_message"

class SubCategory(str, Enum):
    LAPTOP = "Laptop"
    SMARTPHONE = "smartphone"
    PHONE = "phone"
    EARPHONE = "earphone"
    GRAPHIC = "graphic"
    TABLET = "tablet"
    CAMERA = "camera"
    YOGAMAT = "yoga mat"
    DUMBBELLS = "dumbbells"
    CRICKETBAT = "cricket bat"
    BASKETBALL = "basketball"
    TREADMILL = "treadmill"

class ProductAttributes(str, Enum):
    CATEGORY = "category"
    SUBCATEGORY = "subcategory"
    SPECIFICATIONS = "specifications"
    PRODUCT_ID = "product_id"

class OrderAttributes(str, Enum):
    QUANTITY = "quantity"
    ORDER_ID = "order_id"
    PAYMENT_METHOD = "payment_method"
    SHIPPING_ADDRESS = "shipping_address"
    BILLING_ADDRESS = "billing_address"
    RETURN_REASON = "return_reason"
    EXCHANGE_ITEM = "exchange_item"
    EXCHANGE_REASON = "exchange_reason"

class SpecificationsLaptop(str, Enum):
    # laptop
    RAM = "ram"
    STORAGE = "storage"
    PROCESSOR = "processor"
    DISPLAY = "display"
    CAMERA = "camera"
    BATTERY = "battery"
    COLOR = "color"

class DataFrameLookup(str, Enum):
    user_df = "user.json"
    buy_history_df = "buy_history.json"
    category_df = "category.json"
    subcategory_df = "subcategory_df"
    product_df = "product.json"
    specification_df = "specification.json"
    return_df = "return.json"
    review_df = "review.json"

class ConverstionVars(str, Enum):
    max_turns = 5 # max turns per conversation to pull

class LlmVars(str, Enum):
    max_calls = 3

class ModelType(str, Enum):
    openai = "openai"
    gemini = "gemini"