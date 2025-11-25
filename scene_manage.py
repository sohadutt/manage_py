import requests
import sys
import urllib.parse
import json
import time
from typing import List, Dict, Any, Optional

# --- CONFIGURATION ---
BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzY0MTQyMjQ5LCJpYXQiOjE3NjQwNTU4NDksImp0aSI6IjFhNmE4MjY4MGNkMzRhNGU5OTZhOThjMDNhNzNlYzIwIiwidXNlcl9pZCI6MTA3NDEsIm1lbWJlciI6MTE1NTgsIm9yZ2FuaXphdGlvbiI6MjI5NywiaXNfZW1haWxfdmVyaWZpZWQiOnRydWUsImFwcF90eXBlIjoiYmFzZSJ9.K87pkY6GdvmN26HdFqEYatjBTc1McE_XTQkJBRM6TmU"
CONFIGURATOR_ID = "7049"

# If empty, script will fetch ALL scenes from the configurator.
SCENE_ID_LIST = [] 
SCENE_OPTION_ID_LIST = ["48988"] # Leave empty to fetch all options per scene
TEXTURE_SEARCH_TERMS = ["Black"] # Display Name (substring match)

# Resolution Settings
RENDER_CONFIG = {
    "aspect_ratio": "1.33",
    "high_reso_x": 3000, "high_reso_y": 2250,
    "low_reso_x": 1500, "low_reso_y": 1125,
    "compressed_reso_x": 1500, "compressed_reso_y": 1125,
    "bg_reso_x": 3000, "bg_reso_y": 2250,
    "preview_reso_x": 1500, "preview_reso_y": 1125,
    "render_reso_x": 3000, "render_reso_y": 2250
}

# --- CONSTANTS ---
BASE_URL = "https://prod.imagine.io/configurator/api/v2"
SCENE_LIST_URL = f"{BASE_URL}/config-scene/?configurator={CONFIGURATOR_ID}&page=1"
RENDER_URL = f"{BASE_URL}/scene-texture-render/"
PATCH_URL = f"{BASE_URL}/scene-texture/"
DETAILS_URL = f"{BASE_URL}/scene/details/{{scene_id}}/"
VIEWS_URL = f"{BASE_URL}/scene-view/?scene={{scene_id}}"

DEFAULT_HEADERS = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "accept-encoding": "gzip, deflate, br",
    "connection": "keep-alive",
    "accept": "application/json",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0"
}

# --- UI HELPERS ---
def print_header(title: str):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def print_progress(iteration, total, prefix='', suffix='', decimals=1, length=40):
    """Call in a loop to create terminal progress bar"""
    if total == 0:
        return
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    if iteration == total:
        sys.stdout.write('\n')
    sys.stdout.flush()

# --- NETWORK HELPERS ---
def get_paginated_data(session: requests.Session, start_url: str, description: str = "Fetching data") -> List[Dict[str, Any]]:
    all_results = []
    current_url = start_url
    
    # First request to get total count
    try:
        init_resp = session.get(current_url)
        init_resp.raise_for_status()
        data = init_resp.json()
        total_count = data.get("count", 0)
        all_results.extend(data.get("results", []))
        current_url = data.get("next_link")
    except Exception as e:
        print(f"Error initializing fetch: {e}")
        return []

    if total_count == 0:
        return all_results

    # Loop for remaining pages
    while current_url:
        print_progress(len(all_results), total_count, prefix=description, suffix=f"({len(all_results)}/{total_count})")
        
        try:
            resp = session.get(current_url)
            resp.raise_for_status()
            data = resp.json()
            all_results.extend(data.get("results", []))
            current_url = data.get("next_link")
        except Exception:
            # Simple retry logic could go here
            break

    print_progress(total_count, total_count, prefix=description, suffix="Complete")
    return all_results

def get_scene_ancillary_data(session: requests.Session, scene_id: str) -> Dict[str, Any]:
    """Fetches JSON blob, Store ID, and View ID for a specific scene."""
    result: Dict[str, Any] = {"json_content": None, "store_id": None, "sceneview_id": None}
    
    print(f"   > Resolving details for Scene {scene_id}...")

    # 1. Details & JSON
    try:
        resp = session.get(DETAILS_URL.format(scene_id=scene_id))
        resp.raise_for_status()
        details = resp.json()
        result["store_id"] = str(details.get("store", "18340")) # Fallback ID
        
        if details.get("json_file"):
            file_resp = session.get(details["json_file"])
            file_resp.raise_for_status()
            result["json_content"] = file_resp.content
        else:
            print("     [!] Scene has no JSON file.")
            return result # Abort early if no JSON
    except Exception as e:
        print(f"     [!] Details Error: {e}")
        return result

    # 2. Scene View
    try:
        resp = session.get(VIEWS_URL.format(scene_id=scene_id))
        resp.raise_for_status()
        views = resp.json().get("results", [])
        if views:
            result["sceneview_id"] = str(views[0].get("id"))
        else:
            result["sceneview_id"] = scene_id # Fallback
    except Exception:
        result["sceneview_id"] = scene_id

    return result

# --- ACTIONS ---
def patch_texture_property(session, item, field, value):
    url = f"{PATCH_URL}{item['id']}/"
    nested_data = {
        "id": int(item['data_id']) if item['data_id'] else None,
        "scene_id": int(item['scene_id']) if item['scene_id'] else None,
        field: value
    }
    payload = {
        'id': (None, str(item['id'])),
        'configurator': (None, CONFIGURATOR_ID),
        field: (None, 'true' if value else 'false'),
        'data': (None, json.dumps(nested_data))
    }
    try:
        r = session.patch(url, files=payload)
        r.raise_for_status()
        return True
    except:
        return False

def send_render_request(session, item, ancillary):
    payload = {
        "configurator": CONFIGURATOR_ID,
        "scene": item['scene_id'],
        "sceneview": item['sceneview'] if item['sceneview'] else ancillary['sceneview_id'],
        "texture": item['id'],
        "store": item['store'] if item['store'] else ancillary['store_id'],
        "json_data": json.dumps(RENDER_CONFIG)
    }
    files = {"json_file": ("json_file.json", ancillary['json_content'], "application/json")}
    
    try:
        r = session.post(RENDER_URL, data=payload, files=files)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"\n     [!] Render Error: {e}")
        return False

# --- CORE LOGIC ---
def fetch_target_textures(session):
    # 1. Determine Scenes
    target_scenes = SCENE_ID_LIST
    if not target_scenes:
        print_header("Fetching All Configurator Scenes")
        scenes_data = get_paginated_data(session, SCENE_LIST_URL, "Scenes")
        target_scenes = [str(s['id']) for s in scenes_data]
        print(f"   > Total Scenes Found: {len(target_scenes)}")
    
    if not target_scenes:
        return []

    # 2. Fetch Textures (Batch)
    print_header("Fetching Scene Textures")
    all_textures = []
    
    # Calculate total operations for progress bar
    total_ops = len(target_scenes) * (len(SCENE_OPTION_ID_LIST) if SCENE_OPTION_ID_LIST else 1)
    current_op = 0

    for scene_id in target_scenes:
        options = SCENE_OPTION_ID_LIST if SCENE_OPTION_ID_LIST else [None]
        
        for opt_id in options:
            current_op += 1
            query = f"scene={scene_id}" + (f"&sceneoption={opt_id}" if opt_id else "")
            url = f"{BASE_URL}/scene-texture/?{query}&per_page=100"
            
            # Helper to just get results without full pagination print spam
            try:
                # We do a simplified fetch here to keep UI clean during massive batch
                r = session.get(url) 
                if r.status_code == 200:
                    data = r.json()
                    results = data.get("results", [])
                    # Enrich data
                    for item in results:
                        item['fetched_for_scene_id'] = scene_id
                    all_textures.extend(results)
                    
                    # Handle Next Pages silently
                    while data.get("next_link"):
                        r = session.get(data["next_link"])
                        if r.status_code != 200: break
                        data = r.json()
                        page_res = data.get("results", [])
                        for item in page_res: item['fetched_for_scene_id'] = scene_id
                        all_textures.extend(page_res)
            except:
                pass
            
            print_progress(current_op, total_ops, prefix="Scanning", suffix=f"Found: {len(all_textures)}")

    return all_textures

def filter_matches(all_items, search_terms):
    print_header(f"Filtering Results: {search_terms}")
    matches = []
    search_lower = [t.lower() for t in search_terms]
    
    for item in all_items:
        name = item.get("display_name", "").lower()
        if any(term in name for term in search_lower):
            matches.append({
                "display_name": item.get("display_name"),
                "id": str(item.get("id")),
                "scene_id": str(item.get("fetched_for_scene_id")),
                "data_id": str(item.get("data", {}).get("id")) if item.get("data") else None,
                "sceneoption": str(item.get("sceneoption")),
                "store": str(item.get("store")) if item.get("store") else None,
                "sceneview": str(item.get("sceneview")) if item.get("sceneview") else None
            })
    
    print(f"   > Matches Found: {len(matches)}")
    return matches

def run_patch_logic(session, matches):
    print("\n[A] is_enable")
    print("[B] is_updated")
    choice = input("Select Field: ").lower().strip()
    field = "is_enable" if choice == 'a' else "is_updated" if choice == 'b' else None
    
    if not field: return
    
    val = input(f"Set {field} to (T)rue or (F)alse? ").lower().strip()
    bool_val = True if val in ['t', 'y', '1'] else False
    
    print_header(f"Patching {len(matches)} items")
    success_count = 0
    
    for i, item in enumerate(matches):
        if patch_texture_property(session, item, field, bool_val):
            success_count += 1
        print_progress(i + 1, len(matches), prefix="Patching", suffix=f"Success: {success_count}")

def run_render_logic(session, matches):
    # Group by Scene to optimize JSON downloading
    grouped = {}
    for m in matches:
        sid = m['scene_id']
        if sid not in grouped: grouped[sid] = []
        grouped[sid].append(m)
    
    print_header(f"Rendering {len(matches)} Textures across {len(grouped)} Scenes")
    
    total_processed = 0
    total_matches = len(matches)
    
    for scene_id, items in grouped.items():
        # Get Context ONCE per scene
        ancillary = get_scene_ancillary_data(session, scene_id)
        
        if not ancillary['json_content']:
            print(f"     [SKIP] Scene {scene_id} has no valid JSON.")
            total_processed += len(items)
            continue
            
        for item in items:
            send_render_request(session, item, ancillary)
            total_processed += 1
            print_progress(total_processed, total_matches, prefix="Sending", suffix=f"Scene: {scene_id}")

# --- MAIN ---
def main():
    if "YOUR_BEARER_TOKEN" in BEARER_TOKEN:
        print("ERROR: Update BEARER_TOKEN.")
        return

    with requests.Session() as s:
        s.headers.update(DEFAULT_HEADERS)
        
        while True:
            print_header("CONFIGURATOR TOOLBOX")
            print(f" ID: {CONFIGURATOR_ID} | Search: {TEXTURE_SEARCH_TERMS}")
            print(f" Target: {'ALL Scenes' if not SCENE_ID_LIST else f'{len(SCENE_ID_LIST)} Specific Scenes'}")
            print("-" * 60)
            print(" 1. Patch Texture Properties")
            print(" 2. Send Renders (Auto-Fetch JSON/Views)")
            print(" 0. Exit")
            
            c = input("\n Choice > ").strip()
            if c == '0': break
            
            if c in ['1', '2']:
                # 1. Get Data
                raw_data = fetch_target_textures(s)
                if not raw_data: 
                    print("No textures found.")
                    continue
                
                # 2. Filter
                matches = filter_matches(raw_data, TEXTURE_SEARCH_TERMS)
                if not matches:
                    print("No matches for search terms.")
                    continue
                
                # 3. Execute
                if c == '1': run_patch_logic(s, matches)
                if c == '2': run_render_logic(s, matches)

if __name__ == "__main__":
    main()
