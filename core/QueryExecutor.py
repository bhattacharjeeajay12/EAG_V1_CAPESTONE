import pandas as pd
import numpy as np
import os


class QueryExecutor:
    def __init__(self, code_str, data_dir="data", filters=None):
        # Load all available dataframes
        self.filters = filters
        self.df_user = pd.read_json(os.path.join(data_dir, "user.json"))
        self.df_product = pd.read_json(os.path.join(data_dir, "product.json"))
        self.df_specification = pd.read_json(os.path.join(data_dir, "specification.json"))
        self.df_buy_history = pd.read_json(os.path.join(data_dir, "buy_history.json"))
        self.df_category = pd.read_json(os.path.join(data_dir, "category.json"))
        self.df_subcategory = pd.read_json(os.path.join(data_dir, "subcategory.json"))
        self.df_return_history = pd.read_json(os.path.join(data_dir, "return.json"))
        self.df_review = pd.read_json(os.path.join(data_dir, "review.json"))
        self.code_str = code_str
        self.local_vars_mapping = {
            "pd": pd,
            "np": np,
            "df_user": self.df_user,
            "df_product": self.df_product,
            "df_specification": self.df_specification,
            "df_buy_history": self.df_buy_history,
            "df_category": self.df_category,
            "df_subcategory": self.df_subcategory,
            "df_return_history": self.df_return_history,
            "df_review": self.df_review,
        }

    def run_query(self):
        try:
            # df = pd.read_sql_query(query, self.db_connection)
            exec(self.code_str, {}, self.local_vars_mapping)
            # The LLM’s query should produce a DataFrame called df_result
            df_result = self.local_vars_mapping.get("df_result")
            return df_result
        except Exception as e:
            print(f"Error executing query: {e}")
            return None

if __name__ == "__main__":
    sample_code = "import pandas as pd\\\\nimport numpy as np\\\\n\\\\n# Filter products by brand and subcategory\\\\ndf_filtered_products = df_product[\\\\n    (df_product['brand'].str.lower() == 'dell') & \\\\n    (df_product['subcategory_name'].str.lower() == 'laptop')\\\\n].copy()\\\\n\\\\n# Filter specifications for RAM using regex for robust extraction\\\\ndf_ram_specs = df_specification[\\\\n    df_specification['spec_name'].str.lower() == 'ram'\\\\n].copy()\\\\n\\\\n# Extract numeric value using regex (handles '16 GB', '16GB', etc.)\\\\ndf_ram_specs['spec_value_numeric'] = pd.to_numeric(\\\\n    df_ram_specs['spec_value'].str.extract(r'(\\\\d+(?:\\\\.\\\\d+)?)')[0], \\\\n    errors='coerce'\\\\n)\\\\n\\\\n# Filter RAM >= 16\\\\ndf_ram_filtered = df_ram_specs[df_ram_specs['spec_value_numeric'] >= 16]\\\\n\\\\n# Merge to get products with RAM >= 16GB\\\\ndf_with_ram = df_filtered_products.merge(\\\\n    df_ram_filtered[['product_id']], \\\\n    on='product_id', \\\\n    how='inner'\\\\n)\\\\n\\\\n# Sort by price to establish order\\\\ndf_sorted = df_with_ram.sort_values('price_usd').reset_index(drop=True)\\\\n\\\\n# Get the second product with error handling\\\\nif len(df_sorted) >= 2:\\\\n    df_result = pd.DataFrame([df_sorted.iloc[1]])\\\\nelse:\\\\n    # Return empty DataFrame with proper structure if insufficient products\\\\n    df_result = pd.DataFrame(columns=df_sorted.columns)\\\\n\\\\ndf_result",
    QE = QueryExecutor(sample_code, data_dir = "", filters = {"subcategory": "laptop"})
    df_result = QE.run_query()

