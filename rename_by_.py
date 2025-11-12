import os

def rename_files(base_folder):
    for root, dirs, files in os.walk(base_folder):
        for filename in files:
            old_path = os.path.join(root, filename)
            
            name, ext = os.path.splitext(filename)
            
            if '_' not in name:
                continue 
            new_name = name.split('_')[0] + ext
            new_path = os.path.join(root, new_name)
            
            if os.path.exists(new_path):
                print(f"Skipping {old_path} -> {new_name} (file exists)")
                continue
            os.rename(old_path, new_path)
            print(f"Renamed: {filename} -> {new_name}")

if __name__ == "__main__":
    folder = input("Enter the folder path: ").strip()
    if os.path.isdir(folder):
        rename_files(folder)
        print("Renaming complete!")
    else:
        print("Invalid folder path.")
