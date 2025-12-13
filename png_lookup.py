import os
import json
from PIL import Image
from tqdm import tqdm
from colorama import Fore, Style, init

# Initialize colorama for colored output
init(autoreset=True)

def scan_pngs_with_nonempty_first_pixel(main_folder, output_json="pixel_log.json"):
    """
    Scans all PNG images in a folder (recursively) and logs those
    whose first pixel is not fully transparent.
    """
    results = []
    total_checked = 0
    total_included = 0
    log_path = os.path.join(main_folder, output_json)

    # Collect all PNG file paths
    png_files = []
    for root, _, files in os.walk(main_folder):
        for file in files:
            if file.lower().endswith(".png"):
                png_files.append(os.path.join(root, file))

    print(f"\n🔍 {Fore.CYAN}Scanning {len(png_files)} PNG files in {main_folder}...\n")

    # Process each file with a progress bar
    for file_path in tqdm(png_files, desc="Processing images", unit="file", ncols=100, colour="green"):
        total_checked += 1
        try:
            with Image.open(file_path) as img:
                img = img.convert("RGBA")
                pixel = img.getpixel((0, 0))  # (R, G, B, A)

                if pixel[3] > 0:  # Not fully transparent
                    results.append({
                        "file": file_path,
                        "pixel": pixel
                    })
                    total_included += 1

        except Exception as e:
            print(f"{Fore.RED}❌ Error reading {file_path}: {e}")

    # Save JSON results
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    # Summary
    print("\n" + "=" * 60)
    print(f"✅ {Fore.GREEN}Scan Complete!")
    print(f"{Fore.CYAN}Total checked:{Style.RESET_ALL} {total_checked}")
    print(f"{Fore.YELLOW}Included (non-transparent first pixel):{Style.RESET_ALL} {total_included}")
    print(f"{Fore.MAGENTA}Results saved to:{Style.RESET_ALL} {log_path}")
    print("=" * 60 + "\n")

# Example usage:
if __name__ == "__main__":
    MAIN_FOLDER = r"C:\Users\pc\Desktop\fanimation"
    scan_pngs_with_nonempty_first_pixel(MAIN_FOLDER)
