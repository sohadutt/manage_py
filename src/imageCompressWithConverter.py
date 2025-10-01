import os
from PIL import Image

def compress_png_rgba(input_image_path, output_image_path, colors=256):
    try:
        with Image.open(input_image_path) as img:
            # Ensure RGBA
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # Quantize (reduce number of colors) -> lossy but big size reduction
            img = img.quantize(colors=colors).convert("RGBA")

            # Save compressed PNG
            img.save(output_image_path, "PNG", optimize=True, compress_level=9)

            size_kb = os.path.getsize(output_image_path) // 1024
            print(f"✅ {input_image_path} -> {output_image_path} ({size_kb} KB, colors={colors})")

    except Exception as e:
        print(f"❌ Could not process {input_image_path}: {e}")

def compress_images_batch(main_folder, colors=256):
    compressed_root = os.path.join(main_folder, "compressed")
    os.makedirs(compressed_root, exist_ok=True)

    for root, _, files in os.walk(main_folder):
        if os.path.commonpath([compressed_root, root]) == compressed_root:
            continue

        relative_path = os.path.relpath(root, main_folder)
        output_subfolder = os.path.join(compressed_root, relative_path)
        os.makedirs(output_subfolder, exist_ok=True)

        for file in files:
            if file.lower().endswith(".png"):
                input_path = os.path.join(root, file)
                output_path = os.path.join(output_subfolder, file)
                compress_png_rgba(input_path, output_path, colors=colors)

    print(f"\n🎉 All PNGs compressed into '{compressed_root}' as RGBA PNGs")

# Example usage
main_folder = r"C:\Users\pc\Desktop\Config\Dimentions\Maine cottage_Dims\compile\compile_batch2"
compress_images_batch(main_folder, colors=64)
