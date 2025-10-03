import os

def print_tree(startpath, prefix="", ignore=None):
    """
    Recursively print the tree structure of a folder.
    :param startpath: root folder path
    :param prefix: internal use for formatting
    :param ignore: list of folder names to ignore
    """
    if ignore is None:
        ignore = []

    items = [i for i in sorted(os.listdir(startpath)) if i not in ignore]
    for idx, name in enumerate(items):
        path = os.path.join(startpath, name)
        connector = "└── " if idx == len(items) - 1 else "├── "
        print(prefix + connector + name)
        if os.path.isdir(path):
            extension = "    " if idx == len(items) - 1 else "│   "
            print_tree(path, prefix + extension, ignore)

if __name__ == "__main__":
    root_folder = "."  # change to your target folder
    ignore_folders = ["__pycache__", ".git", ".venv", "venv", "dev_docs", ".idea"]  # add folders to ignore
    os.chdir("../")
    print(os.path.abspath(root_folder))
    print_tree(root_folder, ignore=ignore_folders)
