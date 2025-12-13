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

    @staticmethod
    def _sanitize_code(code_str: str) -> str:
        if not isinstance(code_str, str):
            return ""
        normalized = code_str.replace("\r\n", "\n").replace("\r", "\n").strip()
        try:
            normalized = bytes(normalized, "utf-8").decode("unicode_escape")
        except Exception:
            pass
        normalized = normalized.replace("\\\n", "\n")
        return normalized.strip()

    def __init__(self, code_str: str, data_dir: str = "data", filters: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        :param code_str: LLM-produced code (possibly with escaped \n).
        :param data_dir: directory containing data files, e.g. product.csv or product.json
        :param filters: optional mapping like {"df_product": {"subcategory_name": "laptop"}}
                        only equality filters are supported.
        """
        sanitized = self._sanitize_code(code_str)
        self.code_str = sanitized
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
        
        print(f"🔍 Loading {base_name}:")
        print(f"   CSV path: {csv_path} (exists: {os.path.exists(csv_path)})")
        print(f"   JSON path: {json_path} (exists: {os.path.exists(json_path)})")
        if filter_spec:
            print(f"   With filters: {filter_spec}")

        # If CSV exists and a simple equality filter is provided -> use chunks
        if os.path.exists(csv_path) and filter_spec:
            print(f"   → Using chunked CSV read with filters")
            chunks = []
            total_rows_read = 0
            for chunk in pd.read_csv(csv_path, chunksize=100_000, dtype=str):
                total_rows_read += len(chunk)
                mask = pd.Series(True, index=chunk.index)
                for col, val in filter_spec.items():
                    if col not in chunk.columns:
                        print(f"   ⚠️  Column '{col}' not found in data!")
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
            print(f"   → Read {total_rows_read} rows total")
            if chunks:
                result = pd.concat(chunks, ignore_index=True)
                print(f"   ✅ Loaded {len(result)} rows after filtering")
                return result
            # fallback to an empty dataframe with columns from first rows if present
            print(f"   ⚠️  No rows matched filters!")
            try:
                sample = pd.read_csv(csv_path, nrows=1)
                print(f"   → Returning empty DataFrame with {len(sample.columns)} columns")
                return sample.iloc[0:0].copy()
            except Exception:
                print(f"   → Returning completely empty DataFrame")
                return pd.DataFrame()

        # If CSV exists and no filters -> load whole CSV
        if os.path.exists(csv_path):
            print(f"   → Loading full CSV (no filters)")
            result = pd.read_csv(csv_path)
            print(f"   ✅ Loaded {len(result)} rows")
            return result

        # If JSON exists -> load full JSON (assumes it's reasonably sized)
        if os.path.exists(json_path):
            print(f"   → Loading full JSON (no filters)")
            result = pd.read_json(json_path)
            print(f"   ✅ Loaded {len(result)} rows")
            return result

        # Not found -> empty DataFrame
        print(f"   ❌ File not found!")
        return pd.DataFrame()

    def _ensure_loaded(self):
        # load only the DataFrames we need
        print("\n" + "="*60)
        print("📦 Loading DataFrames")
        print("="*60)
        for var_name, base in self.FILE_MAP.items():
            if self._should_load(var_name) and var_name not in self.loaded:
                filter_spec = self.filters.get(var_name)
                df = self._load_file(base, filter_spec)
                self.loaded[var_name] = df
        
        print("\n📊 Summary of Loaded DataFrames:")
        for name, df in self.loaded.items():
            print(f"   {name}: {len(df)} rows × {len(df.columns)} columns")
            if len(df) > 0:
                print(f"      Sample columns: {list(df.columns)[:5]}...")
        print("="*60 + "\n")

    def execute(self) -> Optional[pd.DataFrame]:
        """
        Execute the code string and return df_result (or None on error).
        """
        self._ensure_loaded()
        local_env = {"pd": pd, "np": np}
        # inject loaded DataFrames
        for k, df in self.loaded.items():
            local_env[k] = df

        print("⚙️  Executing query...")
        print(f"   Code length: {len(self.code_str)} chars")
        # preview = self.code_str[:300]
        preview = self.code_str
        print(f"   Code preview:\n{preview}")

        try:
            exec(self.code_str, {}, local_env)
            print("   ✅ Code executed without errors")
        except Exception as e:
            print(f"   ❌ Error executing code: {e}")
            print("   Problematic snippet repr:")
            print(repr(self.code_str[:800]))
            import traceback
            traceback.print_exc()
            return None

        result = local_env.get("df_result")

        if result is None:
            print("   ⚠️  Warning: 'df_result' variable not found in executed code!")
            print(f"   Available variables: {[k for k in local_env.keys() if not k.startswith('_')]}")
            return None

        if isinstance(result, pd.DataFrame):
            print(f"   ✅ Result: {len(result)} rows × {len(result.columns)} columns")
            if len(result) > 0:
                print(f"      Columns: {result.columns.tolist()}")
                print(f"      First row sample: {result.iloc[0].to_dict()}")
            else:
                print(f"      ⚠️  Result is empty (but has columns: {result.columns.tolist()})")
            return result

        # If result is list-like or other, try to coerce to DataFrame
        print(f"   ⚠️  df_result is not a DataFrame, it's {type(result)}")
        print(f"   → Attempting to convert to DataFrame...")
        try:
            converted = pd.DataFrame(result)
            print(f"   ✅ Converted to DataFrame: {len(converted)} rows")
            return converted
        except Exception as e:
            print(f"   ❌ Conversion failed: {e}")
            return None

# Example usage:
if __name__ == "__main__":
    # A sample LLM-produced query (escaped newlines)
    sample_code = (
        "import pandas as pd\\n"
        "df_filtered_products = df_product[(df_product['brand'].str.lower() == 'Apple') & "
        "(df_product['subcategory_name'].str.lower() == 'laptop')].copy()\\n"
        "df_ram_specs = df_specification[df_specification['spec_name'].str.lower() == 'ram'].copy()\\n"
        "df_ram_specs['spec_value_numeric'] = pd.to_numeric(df_ram_specs['spec_value'].str.extract(r'(\d+(?:\.\d+)?)')[0], errors='coerce')\\n"
        "df_ram_filtered = df_ram_specs[df_ram_specs['spec_value_numeric'] >= 8][['product_id']]\\n"
        "df_with_ram = df_filtered_products.merge(df_ram_filtered[['product_id']], on='product_id', how='inner')\\n"
        "df_sorted = df_with_ram.sort_values('price').reset_index(drop=True)\\n"
        "if len(df_sorted) >= 2:\\n"
        "    df_result = pd.DataFrame([df_sorted.iloc[1]])\\n"
        "else:\\n"
        "    df_result = pd.DataFrame(columns=df_sorted.columns)\\n"
    )

    filters = {
        "df_product": {"subcategory_name": "laptop"},
        "df_specification": {"spec_name": "ram"},
    }

    print("="*60)
    print("🧪 TESTING QueryExecutor")
    print("="*60)
    print(f"Data directory: {os.path.abspath('db')}")
    print(f"Filters: {filters}")
    print()

    executor = QueryExecutorSimple(sample_code, data_dir="db", filters=filters)
    res = executor.execute()
    
    print("\n" + "="*60)
    print("🎯 FINAL RESULT")
    print("="*60)
    if res is not None:
        print(f"Shape: {res.shape}")
        print(f"Columns: {res.columns.tolist()}")
        print("\nData:")
        print(res)
    else:
        print("❌ No result returned (execution failed)")
    print("="*60)
