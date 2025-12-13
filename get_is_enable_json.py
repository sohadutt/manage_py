import os
import pandas as pd
import json

# Get the directory where the script is located
script_directory = os.path.dirname(os.path.abspath(__file__))

os.chdir(script_directory)
success = True
if success:
    print(f"✅ Directory changed to: {os.getcwd()}")
else:
    print("❌ Failed to change directory.")

excel_file = 'type 6.xlsx'  
sheet_name = 'Sheet1'  

df = pd.read_excel(excel_file, sheet_name=sheet_name, header=0)
df.columns = df.columns.str.strip().str.lower()  # Clean column names
print("✅ Columns:", df.columns.tolist())
try:
    print("Reading Excel file...")
except Exception as e: 
    print(f"Error: {e}")


print("Columns found in Excel:", df.columns.tolist())

df.columns = df.columns.str.strip().str.lower()
print("📄 Columns found:", df.columns.tolist())


def to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        value = value.strip().lower()
        if value in ['yes', 'y', 'true', '1']:
            return True
        elif value in ['no', 'n', 'false', '0']:
            return False
    return False  


output_list = []

for index, row in df.iterrows():
    item = {
        "id": str(row['id']),          
        "name": str(row['name']),       
        "is_enable": to_bool(row['is_enable'])  
    }
    output_list.append(item)
    print(df.iloc[0])  


with open('status.json', 'w', encoding='utf-8') as f:
    json.dump(output_list, f, indent=4)

print("✅ JSON file created successfully!")

