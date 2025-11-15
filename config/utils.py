from pathlib import Path
import pandas as pd
import os

print("current directory : ", os.getcwd())

BASE_DIR = Path(__file__).resolve().parent.parent

db_root = os.getenv('DB_ROOT', 'db')
db_product = os.getenv('DB_PRODUCT', 'product.json')
db_specification = os.getenv('DB_SPECIFICATION', 'specification.json')

product_path = BASE_DIR / db_root / db_product
spec_path = BASE_DIR / db_root / db_specification

product_db = pd.read_json(product_path)
spec_db = pd.read_json(spec_path)


def _match_subcategory_rows(subcategory: str):
    if not subcategory:
        return product_db.iloc[0:0]
    lowered = subcategory.lower()
    candidates = {
        lowered,
        lowered.rstrip("s"),
        f"{lowered}s",
    }
    return product_db[product_db['subcategory_name'].str.lower().isin(candidates)]


def get_specification_list(subcategory):
    specification_list = []
    product_subcat = _match_subcategory_rows(subcategory)
    if product_subcat.empty:
        return specification_list

    product_id = product_subcat.iloc[0]["product_id"]
    required_spec_df = spec_db[spec_db['product_id'] == product_id]

    for _, row in required_spec_df.iterrows():
        spec_row = {
            "spec_name": row['spec_name'],
            "spec_value": row['spec_value'],
            "spec_name_label": row['spec_name'].replace("_", " "),
            "unit": row['unit'],
            "data_type": row['data_type']
        }
        specification_list.append(spec_row)
    return specification_list
