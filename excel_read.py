import pandas as pd
import json

# -------- SETTINGS --------
file_path = r"C:\Users\pc\Desktop\script\Trimlite Config Template.xlsx"
sheet_name = "Single_Row"
# ---------------------------

# Load sheet
df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

result = []

# Loop over each column except column 0 (skip "Props" column)
for col in df.columns[1:]:
    parent = df.at[0, col]  # Row 0 = object
    outer_frame = df.at[1, col] if pd.notna(df.at[1, col]) else None
    inner_part = df.at[3, col] if pd.notna(df.at[3, col]) else None

    children = []

    # If outer_frame has multiple items, split by comma
    if outer_frame:
        children.extend([s.strip() for s in str(outer_frame).split(",") if s.strip()])

    # Inner part (just one item)
    if inner_part:
        children.append(str(inner_part).strip())

    if pd.notna(parent):  # Only if parent exists
        result.append({
            "object": str(parent).strip(),
            "children": children
        })

# Save to JSON
with open("output.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=4)

print("✅ JSON created: output.json")
