# dev_docs/clear_memory.py

import os
import shutil

def clear_memory_folders():
    base_dir = os.path.dirname(os.path.abspath(__file__))  # path to dev_docs
    memory_dir = os.path.join(base_dir, "..", "memory")   # go up one level to find memory/

    if not os.path.exists(memory_dir):
        print(f"No memory folder found at: {memory_dir}")
        return

    for item in os.listdir(memory_dir):
        item_path = os.path.join(memory_dir, item)
        if os.path.isdir(item_path):
            # Remove folder contents
            for sub_item in os.listdir(item_path):
                sub_item_path = os.path.join(item_path, sub_item)
                if os.path.isfile(sub_item_path) or os.path.islink(sub_item_path):
                    os.remove(sub_item_path)
                elif os.path.isdir(sub_item_path):
                    shutil.rmtree(sub_item_path)
            print(f"Cleared folder: {item_path}")

if __name__ == "__main__":
    clear_memory_folders()
