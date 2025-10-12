"""
Simple QueryExecutor for executing LLM-produced pandas query strings.

Design goals:
- Very small, easy-to-understand code.
- Loads only the DataFrames that are referenced in the code string or explicitly
  requested via `filters` to reduce memory usage.
- Supports CSV and JSON (full read) out of the box. Uses chunked read for CSV
  when a simple equality filter is provided to avoid loading entire file.
- Executes the LLM code with a tight local namespace exposing only:
    - pandas as pd
    - numpy as np
    - loaded df_* DataFrames
- The executed code must assign the final result to a variable named `df_result`.
"""

import os
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

class QueryExecutorSimple:
    FILE_MAP = {
        "df_user": "user",
        "df_product": "product",
        "df_specification": "specification",
        "df_buy_history": "buy_history",
        "df_category": "category",
        "df_subcategory": "subcategory",
        "df_return_history": "return",
        "df_review": "review",
    }

    def __init__(self, code_str: str, data_dir: str = "data", filters: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        :param code_str: LLM-produced code (possibly with escaped \\n).
        :param data_dir: directory containing data files, e.g. product.csv or product.json
        :param filters: optional mapping like {"df_product": {"subcategory_name": "laptop"}}
                        only equality filters are supported.
        """
        try:
            # decode escaped newlines if provided
            self.code_str = code_str.encode("utf-8").decode("unicode_escape")
        except Exception:
            self.code_str = code_str
        self.data_dir = data_dir
        self.filters = filters or {}
        self.loaded = {}  # holds loaded DataFrames

    def _should_load(self, var_name: str) -> bool:
        # Load if var is referenced in code_str or has an explicit filter
        if var_name in self.filters:
            return True
        return var_name in self.code_str

    def _load_file(self, base_name: str, filter_spec: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Try to read CSV (with chunking if filter_spec provided) else JSON.
        filter_spec is a dict of equality filters {col: value} — value can be list for isin.
        """
        csv_path = os.path.join(self.data_dir, base_name + ".csv")
        json_path = os.path.join(self.data_dir, base_name + ".json")

        # If CSV exists and a simple equality filter is provided -> use chunks
        if os.path.exists(csv_path) and filter_spec:
            chunks = []
            for chunk in pd.read_csv(csv_path, chunksize=100_000, dtype=str):
                mask = pd.Series(True, index=chunk.index)
                for col, val in filter_spec.items():
                    if col not in chunk.columns:
                        mask &= False
                        continue
                    series = chunk[col].astype(str).str.lower()
                    if isinstance(val, (list, tuple, set)):
                        vals = [str(v).lower() for v in val]
                        mask &= series.isin(vals)
                    else:
                        mask &= series == str(val).lower()
                filtered = chunk[mask]
                if not filtered.empty:
                    chunks.append(filtered)
            if chunks:
                return pd.concat(chunks, ignore_index=True)
            # fallback to an empty dataframe with columns from first rows if present
            try:
                sample = pd.read_csv(csv_path, nrows=1)
                return sample.iloc[0:0].copy()
            except Exception:
                return pd.DataFrame()

        # If CSV exists and no filters -> load whole CSV
        if os.path.exists(csv_path):
            return pd.read_csv(csv_path)

        # If JSON exists -> load full JSON (assumes it's reasonably sized)
        if os.path.exists(json_path):
            return pd.read_json(json_path)

        # Not found -> empty DataFrame
        return pd.DataFrame()

    def _ensure_loaded(self):
        # load only the DataFrames we need
        for var_name, base in self.FILE_MAP.items():
            if self._should_load(var_name) and var_name not in self.loaded:
                filter_spec = self.filters.get(var_name)
                df = self._load_file(base, filter_spec)
                self.loaded[var_name] = df

    def execute(self) -> Optional[pd.DataFrame]:
        """
        Execute the code string and return df_result (or None on error).
        """
        self._ensure_loaded()
        local_env = {"pd": pd, "np": np}
        # inject loaded DataFrames
        for k, df in self.loaded.items():
            local_env[k] = df
        try:
            exec(self.code_str, {}, local_env)
        except Exception as e:
            print("Error executing code:", e)
            return None

        result = local_env.get("df_result")
        if isinstance(result, pd.DataFrame):
            return result
        # If result is list-like or other, try to coerce to DataFrame
        try:
            return pd.DataFrame(result)
        except Exception:
            return None

# Example usage:
if __name__ == "__main__":
    # A sample LLM-produced query (escaped newlines)
    sample_code = (
        "import pandas as pd\\n"
        "df_filtered_products = df_product[(df_product['brand'].str.lower() == 'dell') & "
        "(df_product['subcategory_name'].str.lower() == 'laptop')].copy()\\n"
        "df_ram_specs = df_specification[df_specification['spec_name'].str.lower() == 'ram'].copy()\\n"
        "df_ram_specs['spec_value_numeric'] = pd.to_numeric(df_ram_specs['spec_value'].str.extract(r'(\\d+(?:\\.\\d+)?)')[0], errors='coerce')\\n"
        "df_ram_filtered = df_ram_specs[df_ram_specs['spec_value_numeric'] >= 16][['product_id']]\\n"
        "df_with_ram = df_filtered_products.merge(df_ram_filtered[['product_id']], on='product_id', how='inner')\\n"
        "df_sorted = df_with_ram.sort_values('price_usd').reset_index(drop=True)\\n"
        "if len(df_sorted) >= 2:\\n"
        "    df_result = pd.DataFrame([df_sorted.iloc[1]])\\n"
        "else:\\n"
        "    df_result = pd.DataFrame(columns=df_sorted.columns)\\n"
    )

    filters = {
        "df_product": {"subcategory_name": "laptop"},
        "df_specification": {"spec_name": "ram"},
    }

    executor = QueryExecutorSimple(sample_code, data_dir=os.path.join("..", "db"), filters=filters)
    res = executor.execute()
    print(res)
