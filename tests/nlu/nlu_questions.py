questions = {
    "ques_1": {  # CONTINUATION
        "CURRENT_MESSAGE": "Show me gaming laptops under $1500",
        "PAST_3_USER_MESSAGES": [
            "I want to buy a laptop",
            "Preferably Dell or HP",
            "Make sure it has at least 16GB RAM"
        ],
        "last_intent": "DISCOVERY",
        "session_entities": {
            "category": "electronics",
            "subcategory": "laptop",
            "product": None,
            "specifications": {"brand": "Dell", "RAM": "16GB"},
            "budget": None,
            "quantity": 1,
            "order_id": None,
            "urgency": None,
            "comparison_items": [],
            "preferences": []
        }
    },
    "ques_2": {  # INTENT_SWITCH
        "CURRENT_MESSAGE": "Where is my order?",
        "PAST_3_USER_MESSAGES": [
            "I want to buy a laptop",
            "Something around $1000",
            "Prefer Dell brand"
        ],
        "last_intent": "DISCOVERY",
        "session_entities": {
            "category": "electronics",
            "subcategory": "laptop",
            "product": "Dell laptop",
            "specifications": {"brand": "Dell"},
            "budget": "$1000",
            "quantity": 1,
            "order_id": None,
            "urgency": None,
            "comparison_items": [],
            "preferences": []
        }
    },
    "ques_3": {  # CONTEXT_SWITCH (REPLACE)
        "CURRENT_MESSAGE": "Actually, show me tablets instead.",
        "PAST_3_USER_MESSAGES": [
            "I want a laptop",
            "Prefer 16GB RAM",
            "Budget around $1200"
        ],
        "last_intent": "DISCOVERY",
        "session_entities": {
            "category": "electronics",
            "subcategory": "laptop",
            "product": None,
            "specifications": {"RAM": "16GB"},
            "budget": "$1200",
            "quantity": None,
            "order_id": None,
            "urgency": None,
            "comparison_items": [],
            "preferences": []
        }
    },
    "ques_4": {  # CONTEXT_SWITCH (ADD)
        "CURRENT_MESSAGE": "Also show me smartphones.",
        "PAST_3_USER_MESSAGES": [
            "I need a laptop",
            "With 512GB SSD",
            "Budget under $1500"
        ],
        "last_intent": "DISCOVERY",
        "session_entities": {
            "category": "electronics",
            "subcategory": "laptop",
            "product": None,
            "specifications": {"SSD": "512GB"},
            "budget": "$1500",
            "quantity": None,
            "order_id": None,
            "urgency": None,
            "comparison_items": [],
            "preferences": []
        }
    },
    "ques_5": {  # CONTEXT_SWITCH (COMPARE)
        "CURRENT_MESSAGE": "Compare it with HP laptops.",
        "PAST_3_USER_MESSAGES": [
            "I’m looking at Dell laptops",
            "Prefer 15 inch screen",
            "Budget $1200"
        ],
        "last_intent": "DISCOVERY",
        "session_entities": {
            "category": "electronics",
            "subcategory": "laptop",
            "product": "Dell laptop",
            "specifications": {"screen": "15 inch"},
            "budget": "$1200",
            "quantity": 1,
            "order_id": None,
            "urgency": None,
            "comparison_items": [],
            "preferences": []
        }
    },
    "ques_6": {  # CONTEXT_SWITCH (SEPARATE)
        "CURRENT_MESSAGE": "Now I also need a blender.",
        "PAST_3_USER_MESSAGES": [
            "I want to buy running shoes",
            "Prefer Adidas brand",
            "Budget $200"
        ],
        "last_intent": "DISCOVERY",
        "session_entities": {
            "category": "sports",
            "subcategory": "shoes",
            "product": "Adidas running shoes",
            "specifications": {},
            "budget": "$200",
            "quantity": 1,
            "order_id": None,
            "urgency": None,
            "comparison_items": [],
            "preferences": []
        }
    },
    "ques_7": {  # ADDITION
        "CURRENT_MESSAGE": "Also, tell me about the return policy.",
        "PAST_3_USER_MESSAGES": [
            "I want a laptop",
            "Prefer Lenovo brand",
            "Budget $1000"
        ],
        "last_intent": "DISCOVERY",
        "session_entities": {
            "category": "electronics",
            "subcategory": "laptop",
            "product": "Lenovo laptop",
            "specifications": {"brand": "Lenovo"},
            "budget": "$1000",
            "quantity": 1,
            "order_id": None,
            "urgency": None,
            "comparison_items": [],
            "preferences": []
        }
    },
    "ques_8": {  # UNCLEAR
        "CURRENT_MESSAGE": "What about that one?",
        "PAST_3_USER_MESSAGES": [
            "I want a laptop",
            "Prefer 13 inch MacBook",
            "Budget $1500"
        ],
        "last_intent": "DISCOVERY",
        "session_entities": {
            "category": "electronics",
            "subcategory": "laptop",
            "product": "Apple MacBook",
            "specifications": {"screen": "13 inch"},
            "budget": "$1500",
            "quantity": 1,
            "order_id": None,
            "urgency": None,
            "comparison_items": [],
            "preferences": []
        }
    }
}
