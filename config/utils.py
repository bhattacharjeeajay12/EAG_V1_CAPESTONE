import pandas as pd
import os

print("current directory : ", os.getcwd())
db_root = os.getenv('DB_ROOT', 'db')
db_product = os.getenv('DB_PRODUCT', 'product.json')
db_specification = os.getenv('DB_SPECIFICATION', 'specification.json')

product_db = pd.read_json(os.path.join("..", db_root, db_product))
spec_db = pd.read_json(os.path.join("..", db_root, db_specification))

def get_specification_list(subcategory):
    specification_list = list()
    product_subcat = product_db[product_db['subcategory_name'] == subcategory]
    product_id = product_subcat.loc[0]["product_id"]
    required_spec_df = spec_db[spec_db['product_id'] == product_id]

    for _, row in required_spec_df.iterrows():
        spec_row = {"spec_name": row['spec_name'], "spec_value": row['spec_value'], "spec_name_label": row['spec_name'].replace("_", " "), "unit": row['unit'], "data_type": row['data_type']}
        specification_list.append(spec_row)
    return specification_list
