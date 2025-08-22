# E-Commerce Database Schema

This schema represents a miniature relational database for an e-commerce platform. It includes tables for users, products, categories, orders, returns, and reviews, with appropriate relationships between them.

## Schema Structure

### USER
| user_id | first_name | second_name | email | phone | address |
|---------|------------|-------------|-------|-------|---------|
| PRIMARY KEY | | | | | |

Stores information about registered users of the e-commerce platform.

### Buy history
| order_id | user_id | date | product_id | payment_method | shipping_address | return_eligible_date | quantity |
|----------|---------|------|------------|----------------|------------------|----------------------|----------|
| PRIMARY KEY | FOREIGN KEY | | FOREIGN KEY | | | | |

Records all purchase transactions. Links users to products they've purchased.

### category
| category_id | category_name |
|-------------|---------------|
| PRIMARY KEY | |

Main product categories (Electronics, Utensils, Books, Sports).

### subcategory
| subcategory_id | category_id | subcategory_name |
|----------------|-------------|------------------|
| PRIMARY KEY | FOREIGN KEY | |

Subdivisions within each main category. Each category has multiple subcategories.

### product
| product_id | subcategory_id | product_name | items_included | price | product_description | return_window |
|------------|----------------|--------------|----------------|-------|---------------------|---------------|
| PRIMARY KEY | FOREIGN KEY | | | | | |

Product details including pricing, descriptions, and which subcategory they belong to.

### Specification
| spec_id | product_id | spec_name | spec_value |
|---------|------------|-----------|------------|
| PRIMARY KEY | FOREIGN KEY | | |

Technical specifications for products (e.g., color, RAM, screen size for electronics).

### Return
| return_id | buy_order_id | return_request_date | return_reason | return_status |
|-----------|--------------|---------------------|---------------|---------------|
| PRIMARY KEY | FOREIGN KEY | | | |

Tracks product returns, linked to specific orders.

### Review
| review_id | user_id | product_id | rating | review_title | review_text | review_date | helpful_votes |
|-----------|---------|------------|--------|--------------|-------------|-------------|---------------|
| PRIMARY KEY | FOREIGN KEY | FOREIGN KEY | | | | | |

Customer reviews for products, linked to both users and products.

## Relationships

- Users make purchases (Buy history)
- Users write reviews (Review)
- Categories contain subcategories
- Subcategories contain products
- Products have specifications
- Products can be purchased (Buy history)
- Products can be reviewed (Review)
- Orders can be returned (Return)
