from config.enums import Agents as agent
from config.enums import Categories as category
from config.enums import SubCategory as subcategory
from config.enums import WorkstreamState as ws
from config.enums import SpecificationsLaptop as spec
from config.enums import ProductAttributes as pattribute
from config.utils import get_specification_list

# Simple numeric constant (no need for Enum)
MAX_TURNS_TO_PULL = 5

# Initial state for new workstreams
INITIAL_STATE = ws.NEW.value

# Thresholds as dictionary (easier to extend)
INTENT_THRESHOLDS = {
    agent.DISCOVERY.value: 0.5,
    agent.ORDER.value: 0.5
}

# Better as dictionary for flexibility
MANDATORY_SLOTS = {
    agent.DISCOVERY.value: [pattribute.SUBCATEGORY.value],
    agent.ORDER.value: [pattribute.PRODUCT_ID.value, "quantity"],
    agent.PAYMENT.value: ["order_id"],
    agent.EXCHANGE.value: ["order_id"],
    agent.RETURN.value: ["order_id"],
}

CATEGORIES = {
    category.ELECTRONICS.value: [subcategory.LAPTOP.value, subcategory.SMARTPHONE.value, subcategory.EARPHONE.value, subcategory.GRAPHIC.value, subcategory.TABLET.value, subcategory.CAMERA.value],
    category.SPORTS.value: [subcategory.YOGAMAT.value, subcategory.DUMBBELLS.value, subcategory.CRICKETBAT.value, subcategory.BASKETBALL.value, subcategory.TREADMILL.value]
}

SPECIAL_SLOTS = {
    subcategory.LAPTOP.value: [spec.RAM.value, spec.STORAGE.value, spec.PROCESSOR.value, spec.DISPLAY.value],
    subcategory.PHONE.value: [spec.STORAGE.value, spec.CAMERA.value, spec.BATTERY.value, spec.COLOR.value],
}

_laptop_specs = get_specification_list(subcategory.LAPTOP.value)
_dumbbell_specs = get_specification_list(subcategory.DUMBBELLS.value)

SPECIFICATIONS = {
    subcategory.LAPTOP.value: _laptop_specs,
    subcategory.DUMBBELLS.value: _dumbbell_specs,
}

