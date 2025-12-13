import os
import shutil
import json

def organize_images_by_copying():
    """
    Copies PNG files to a new organized structure. It now correctly checks the
    entire file path (including subfolders) for the 'baselayer' keyword.
    """
    # 1. Get source and destination folders
    source_dir = input("Enter the full path of the folder to organize (originals will be safe): ")
    dest_dir = input("Enter the full path for the destination folder (where copies will be saved): ")

    if not os.path.isdir(source_dir):
        print(f"\n❌ Error: The source directory '{source_dir}' does not exist.")
        return

    # 2. Define categories and initialize counters
    categories = ["Narrow Reed", "Clear Glass", "Satin Etch"]
    other_folder = "others"
    copy_log = []
    total_files_scanned = 0
    copied_png_count = 0
    
    print("\nCreating destination folders...")
    for category in categories:
        os.makedirs(os.path.join(dest_dir, category), exist_ok=True)
    os.makedirs(os.path.join(dest_dir, other_folder), exist_ok=True)
    print("Folders are ready.")

    # 3. Walk through source directory to find and copy files
    print("\nScanning and copying files...")
    for root, dirs, files in os.walk(source_dir):
        total_files_scanned += len(files)
        
        for file in files:
            if file.lower().endswith('.png'):
                original_path = os.path.join(root, file)
                copied = False
                
                for category in categories:
                    if category.lower() in original_path.lower():
                        
                        # MODIFIED: Check the full original_path for 'baselayer', not just the filename.
                        if 'baselayer' in original_path.lower():
                            final_dest_dir = os.path.join(dest_dir, category, 'baselayer')
                        else:
                            final_dest_dir = os.path.join(dest_dir, category)
                        
                        os.makedirs(final_dest_dir, exist_ok=True)
                        dest_path = os.path.join(final_dest_dir, file)
                        
                        copy_log.append({"original_path": original_path, "new_path": dest_path})
                        shutil.copy2(original_path, dest_path)
                        print(f"Copied: '{file}' -> '{os.path.relpath(final_dest_dir, dest_dir)}'")
                        copied = True
                        copied_png_count += 1
                        break
                
                if not copied:
                    # MODIFIED: Also check the full original_path for 'others' category.
                    if 'baselayer' in original_path.lower():
                        final_dest_dir = os.path.join(dest_dir, other_folder, 'baselayer')
                    else:
                        final_dest_dir = os.path.join(dest_dir, other_folder)

                    os.makedirs(final_dest_dir, exist_ok=True)
                    dest_path = os.path.join(final_dest_dir, file)
                    
                    copy_log.append({"original_path": original_path, "new_path": dest_path})
                    shutil.copy2(original_path, dest_path)
                    print(f"Copied: '{file}' -> '{os.path.relpath(final_dest_dir, dest_dir)}'")
                    copied_png_count += 1
    
    # 4. Save the log file and show final counts
    if copy_log:
        log_file_path = os.path.join(dest_dir, 'copy_log.json')
        with open(log_file_path, 'w') as f:
            json.dump(copy_log, f, indent=4)
        print(f"\n✅ Organization complete!")
        print(f"   - Scanned a total of {total_files_scanned} files.")
        print(f"   - Copied {copied_png_count} PNG files.")
        print(f"   - A log file was saved to: {log_file_path}")
    else:
        print(f"\nScan complete. Scanned {total_files_scanned} files but found no PNGs to copy.")


def cleanup_organized_files():
    """
    Deletes the copied files and the log file based on a copy_log.json.
    """
    log_file_path = input("Enter the full path to the 'copy_log.json' file to clean up: ")

    if not os.path.exists(log_file_path):
        print(f"\n❌ Error: Log file not found at '{log_file_path}'.")
        return

    try:
        with open(log_file_path, 'r') as f:
            copy_log = json.load(f)
    except json.JSONDecodeError:
        print("\n❌ Error: The log file is corrupted or not a valid JSON.")
        return

    print("\nStarting to delete copied files...")
    deleted_count = 0
    for record in copy_log:
        copied_file_path = record['new_path']

        if os.path.exists(copied_file_path):
            os.remove(copied_file_path)
            print(f"Deleted: '{os.path.basename(copied_file_path)}'")
            deleted_count += 1
        else:
            print(f"Skipped: '{os.path.basename(copied_file_path)}' was already deleted or moved.")

    os.remove(log_file_path)
    print(f"\n✅ Cleanup complete! Deleted {deleted_count} copied files and removed the log file.")
    print("The empty folders remain, you can delete them manually if needed.")


# Main menu to let the user choose an action
if __name__ == "__main__":
    while True:
        print("\n--- File Organizer Menu ---")
        print("1. Organize PNG files (by copying)")
        print("2. Clean up organized copies (deletes copies)")
        print("3. Exit")
        choice = input("Please choose an option (1, 2, or 3): ")

        if choice == '1':
            organize_images_by_copying()
            break
        elif choice == '2':
            cleanup_organized_files()
            break
        elif choice == '3':
            print("Exiting.")
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")