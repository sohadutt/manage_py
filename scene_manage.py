import requests
import sys
import urllib.parse
import json
import time
import os
import gzip
from datetime import datetime
from typing import List, Dict, Any

# --- CONFIGURATION ---
BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzY1OTUwMzM3LCJpYXQiOjE3NjU4NjM5MzcsImp0aSI6ImFmNDVkOTU0MGEzODRhNjg4ODQ2MWE2ZDJhYjMxZmJkIiwidXNlcl9pZCI6MTA3NDEsIm1lbWJlciI6MTE1NTgsIm9yZ2FuaXphdGlvbiI6MjI5NywiaXNfZW1haWxfdmVyaWZpZWQiOnRydWUsImFwcF90eXBlIjoiYmFzZSJ9.ADxKJsTBb1C2ky26XcofHT9x9ipSxjIkgPJrDAixROg"
CONFIGURATOR_ID = "7059"

SCENE_ID_LIST = [] 
SCENE_OPTION_ID_LIST = ["49960"] 
TEXTURE_SEARCH_TERMS = ["Matte White", "Stainless Steel", "Gold"] 

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
RENDER_STORE_LIST_URL = f"{BASE_URL}/render-store-list/?configurator={CONFIGURATOR_ID}&page=1"

RENDER_URL = f"{BASE_URL}/scene-texture-render/"
RE_RENDER_URL = f"{BASE_URL}/scene-texture-re-render/"
PATCH_URL = f"{BASE_URL}/scene-texture/"
DETAILS_URL = f"{BASE_URL}/scene/details/{{scene_id}}/"
VIEWS_URL = f"{BASE_URL}/scene-view/?scene={{scene_id}}"
RENDER_STATUS_URL = f"{BASE_URL}/render-status-data/"

DEFAULT_HEADERS = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "accept-encoding": "gzip, deflate", 
    "connection": "keep-alive",
    "accept": "application/json",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0"
}

# --- OPTIONAL IMPORTS ---
try: import brotli
except ImportError: brotli = None
try: import zstandard as zstd
except ImportError: zstd = None

# --- UI HELPERS ---
def print_header(title: str):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def print_progress(iteration, total, prefix='', suffix='', decimals=1, length=40):
    if total == 0: return
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    if iteration == total: sys.stdout.write('\n')
    sys.stdout.flush()

def log_error(response: requests.Response, context: str):
    print(f"\n [!] ERROR during {context}")
    print(f"     Status Code: {response.status_code}")
    if response.status_code == 401:
        print_header("CRITICAL ERROR: TOKEN EXPIRED")
        print(" [!!!] The Bearer Token is invalid or expired.")
        sys.exit(1)
    try:
        err_json = response.json()
        print(f"     Server Message: {json.dumps(err_json, indent=2)}")
    except:
        print(f"     Server Response: {response.text[:200]}") 

# --- NETWORK HELPERS ---
def get_paginated_data(session: requests.Session, start_url: str, description: str = "Fetching data") -> List[Dict[str, Any]]:
    all_results = []
    current_url = start_url
    
    # 1. Fetch First Page
    try:
        init_resp = session.get(current_url)
        init_resp.raise_for_status()
        data = init_resp.json()
        total_count = data.get("count", 0)
        all_results.extend(data.get("results", []))
        current_url = data.get("next_link")
    except requests.exceptions.HTTPError:
        log_error(init_resp, description)
        current_url = None
    except Exception as e:
        print(f" [!] Network Error: {e}")
        current_url = None

    if total_count == 0: return all_results

    # 2. Loop Next Links
    while current_url:
        print_progress(len(all_results), total_count, prefix=description, suffix=f"({len(all_results)}/{total_count})")
        try:
            resp = session.get(current_url)
            resp.raise_for_status()
            data = resp.json()
            all_results.extend(data.get("results", []))
            current_url = data.get("next_link")
        except requests.exceptions.HTTPError:
            log_error(resp, "Fetching Next Page")
            break
        except Exception:
            break
    
    print_progress(total_count, total_count, prefix=description, suffix="Complete")
    return all_results

def robust_decompress(raw_bytes: bytes) -> bytes:
    if brotli:
        try: return brotli.decompress(raw_bytes)
        except: pass
    try: return gzip.decompress(raw_bytes)
    except: pass
    if zstd:
        try: 
            dctx = zstd.ZstdDecompressor()
            return dctx.decompress(raw_bytes, max_output_size=104857600)
        except: pass
    try: import lzma; return lzma.decompress(raw_bytes)
    except: pass
    try: import zlib; return zlib.decompress(raw_bytes)
    except: pass
    try: import bz2; return bz2.decompress(raw_bytes)
    except: pass
    return raw_bytes

# --- STORE ID LOGIC ---
def get_store_id_map_from_render_list(session: requests.Session) -> Dict[str, str]:
    print_header("Resolving Store IDs from Render List")
    store_map = {}
    render_list_data = get_paginated_data(session, RENDER_STORE_LIST_URL, "Fetching Render Store List")
    
    for item in render_list_data:
        store_id = str(item.get("id"))
        scene_id = str(item.get("scene"))
        if store_id and scene_id and store_id != 'None' and scene_id != 'None':
            store_map[scene_id] = store_id
            
    print(f" [OK] Mapped {len(store_map)} Scenes to Store IDs.")
    return store_map

def get_scene_ancillary_data(session: requests.Session, scene_id: str, store_map: Dict[str, str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {"json_content": None, "store_id": None, "sceneview_id": None, "local_path": None}
    
    if scene_id in store_map:
        result["store_id"] = store_map[scene_id]
    
    try:
        resp = session.get(DETAILS_URL.format(scene_id=scene_id))
        if resp.status_code == 200:
            details = resp.json()
            if not result["store_id"]:
                fallback = str(details.get("store"))
                if fallback and fallback != 'None':
                    result["store_id"] = fallback
            
            json_url = details.get("json_file")
            if json_url:
                file_resp = session.get(json_url)
                if file_resp.status_code == 200:
                    raw_content = file_resp.content
                    final_json_obj = None
                    try:
                        final_json_obj = file_resp.json()
                    except ValueError:
                        decompressed_bytes = robust_decompress(raw_content)
                        try: final_json_obj = json.loads(decompressed_bytes)
                        except: pass

                    if final_json_obj is not None:
                        clean_bytes = json.dumps(final_json_obj, indent=4).encode('utf-8')
                        result["json_content"] = clean_bytes
                        try:
                            today_str = datetime.now().strftime("%Y-%m-%d")
                            save_dir = os.path.join("json_dump", today_str, CONFIGURATOR_ID, str(scene_id))
                            os.makedirs(save_dir, exist_ok=True)
                            file_path = os.path.join(save_dir, f"scene_{scene_id}.json")
                            with open(file_path, 'wb') as f: f.write(clean_bytes)
                            result["local_path"] = file_path
                        except Exception: pass
    except Exception: pass

    try:
        resp = session.get(VIEWS_URL.format(scene_id=scene_id))
        if resp.status_code == 200:
            views = resp.json().get("results", [])
            if views: result["sceneview_id"] = str(views[0].get("id"))
            else: result["sceneview_id"] = scene_id
        else: result["sceneview_id"] = scene_id
    except Exception: result["sceneview_id"] = scene_id

    return result

# --- ACTION LOGIC ---
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
    except requests.exceptions.HTTPError:
        return False
    except Exception:
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
    json_bytes = ancillary.get('json_content')
    local_path = ancillary.get('local_path')
    try:
        if json_bytes:
            files = {"json_file": ("scene_data.json", json_bytes, "application/json")}
            r = session.post(RENDER_URL, data=payload, files=files)
            r.raise_for_status()
            return True
        elif local_path and os.path.exists(local_path):
            with open(local_path, 'rb') as f_bin:
                files = {"json_file": ("scene_data.json", f_bin, "application/json")}
                r = session.post(RENDER_URL, data=payload, files=files)
                r.raise_for_status()
                return True
        return False
    except Exception as e:
        print(f"\n     [!] Render Error: {e}")
        return False

# --- RE-RENDER LOGIC (OPTION 3) ---
def trigger_re_render(session, render_id):
    multipart_data = {
        "render_id": (None, str(render_id))
    }
    try:
        r = session.post(RE_RENDER_URL, files=multipart_data)
        r.raise_for_status()
        return True
    except requests.exceptions.HTTPError:
        log_error(r, f"Re-rendering ID {render_id}")
        return False
    except Exception as e:
        print(f" [!] Error: {e}")
        return False

def fetch_render_status_items(session, unique_store_ids):
    collected_items = []
    print_header("Scanning Render Status Data")
    
    # COUNTING VARIABLES
    total_scanned = 0
    failed_count = 0
    
    options = SCENE_OPTION_ID_LIST if SCENE_OPTION_ID_LIST else [None]
    total_steps = len(unique_store_ids) * len(options)
    current_step = 0
    
    for store_id in unique_store_ids:
        for opt_id in options:
            current_step += 1
            print(f" > Checking Store {store_id} | Option {opt_id} ({current_step}/{total_steps})...")
            
            base_query = f"store_id={store_id}&is_render=true&page=1&sort=-created_at"
            if opt_id: base_query += f"&sceneoption={opt_id}"
            
            target_url = f"{RENDER_STATUS_URL}?{base_query}"
            items = get_paginated_data(session, target_url, description="   Downloading Status list")
            
            for item in items:
                total_scanned += 1
                
                # --- FILTERING LOGIC ---
                status_val = str(item.get("status"))
                scene_val = str(item.get("scene"))
                
                # 1. SCENE ID FILTER (If SCENE_ID_LIST is not empty)
                if SCENE_ID_LIST and scene_val not in SCENE_ID_LIST:
                    continue

                # 2. STATUS FILTER (Strictly "3")
                if status_val == "3":
                    failed_count += 1
                    if item.get("renders"):
                        collected_items.append({
                            "render_id": item.get("renders"),
                            "display_name": item.get("display_name"),
                            "store_id": item.get("store"),
                            "status": status_val, 
                            "sceneoption": item.get("scene_option"),
                            "scene": scene_val,
                            "original_data": item
                        })
    
    print("-" * 60)
    print(f" SCAN RESULTS:")
    print(f" Total Scanned: {total_scanned}")
    print(f" Failed (Status 3): {failed_count}")
    if SCENE_ID_LIST:
        print(f" (Filtered by {len(SCENE_ID_LIST)} specific scenes)")
    print("-" * 60)
    
    return collected_items

def run_send_failed_logic(session, matches):
    # 1. Resolve Stores
    store_map = get_store_id_map_from_render_list(session)
    
    if SCENE_ID_LIST:
        target_stores = set()
        for s_id in SCENE_ID_LIST:
            if s_id in store_map: target_stores.add(store_map[s_id])
        unique_stores = list(target_stores)
        print(f" [i] Filtered to {len(unique_stores)} stores based on SCENE_ID_LIST.")
    else:
        unique_stores = list(set(store_map.values()))
        print(f" [i] Targeting ALL {len(unique_stores)} detected stores.")

    if not unique_stores:
        print(" [!] No Store IDs found. Cannot check render status.")
        return

    # 2. Fetch Data (Includes Filtering for Status 3 and Scene ID)
    render_list = fetch_render_status_items(session, unique_stores)
    
    if not render_list:
        print("No FAILED items found matching criteria.")
        return

    # 3. NO DEDUPLICATION (As requested)
    items_to_process = render_list
    print(f" [i] Found {len(items_to_process)} failed items (No deduplication).")

    # 4. Save Log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"failed_renders_log_{timestamp}.json"
    
    try:
        with open(log_filename, 'w', encoding='utf-8') as f:
            json.dump(items_to_process, f, indent=4)
        print_header(f"Log Saved: {log_filename}")
    except Exception as e:
        print(f" [!] Failed to save log: {e}")

    # 5. SINGLE CONFIRMATION
    print(f"\nReady to trigger re-renders for {len(items_to_process)} FAILED items.")
    confirm = input(" >>> Do you want to proceed? (y/n): ").strip().lower()
    
    if confirm not in ['y', 'yes']:
        print("Aborted.")
        return

    success_count = 0
    for i, item in enumerate(items_to_process):
        r_id = item['render_id']
        name = item['display_name']
        s_id = item.get('scene', 'Unknown')
        
        if trigger_re_render(session, r_id):
            success_count += 1
        print_progress(i + 1, len(items_to_process), prefix="Re-rendering", suffix=f"OK: {success_count} | {name} (Scene: {s_id})")

# --- MAIN ---
def fetch_target_textures(session):
    target_scenes = SCENE_ID_LIST
    if not target_scenes:
        print_header("Fetching All Configurator Scenes")
        scenes_data = get_paginated_data(session, SCENE_LIST_URL, "Scenes")
        target_scenes = [str(s['id']) for s in scenes_data if s.get("is_enable")]
        print(f"   > Total Enabled Scenes Found: {len(target_scenes)} from Total: {len(scenes_data)}")
    
    if not target_scenes: return []

    print_header("Fetching Scene Textures")
    all_textures = []
    total_ops = len(target_scenes) * (len(SCENE_OPTION_ID_LIST) if SCENE_OPTION_ID_LIST else 1)
    current_op = 0

    for scene_id in target_scenes:
        options = SCENE_OPTION_ID_LIST if SCENE_OPTION_ID_LIST else [None]
        for opt_id in options:
            current_op += 1
            query = f"scene={scene_id}" + (f"&sceneoption={opt_id}" if opt_id else "")
            url = f"{BASE_URL}/scene-texture/?{query}&per_page=100"
            try:
                r = session.get(url) 
                if r.status_code == 200:
                    data = r.json()
                    results = data.get("results", [])
                    for item in results: item['fetched_for_scene_id'] = scene_id
                    all_textures.extend(results)
                    while data.get("next_link"):
                        r = session.get(data["next_link"])
                        if r.status_code != 200: break
                        data = r.json()
                        page_res = data.get("results", [])
                        for item in page_res: item['fetched_for_scene_id'] = scene_id
                        all_textures.extend(page_res)
            except Exception: pass
            print_progress(current_op, total_ops, prefix="Scanning", suffix=f"Found: {len(all_textures)}")
    return all_textures

def filter_matches(all_items, search_terms, require_enabled=False):
    matches = []
    filter_desc = search_terms if search_terms else 'All Items'
    if require_enabled: filter_desc = str(filter_desc) + " (Only Enabled)"    
    print_header(f"Filtering Results: {filter_desc}")
    
    search_lower = [t.lower() for t in search_terms] if search_terms else []

    for item in all_items:
        name = item.get("display_name", "").lower()
        has_name_match = True
        if search_lower: has_name_match = any(term in name for term in search_lower)
        is_enabled = item.get("data", {}).get("is_enable")
        has_enabled_match = True
        if require_enabled:
            if is_enabled is not True: has_enabled_match = False

        if has_name_match and has_enabled_match:
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
    store_map = get_store_id_map_from_render_list(session)
    
    # Group by Scene
    scenes = {}
    for m in matches:
        s_id = m['scene_id']
        if s_id not in scenes: scenes[s_id] = []
        scenes[s_id].append(m)
    
    print_header(f"Preparing {len(matches)} Textures across {len(scenes)} Scenes")
    
    confirm = input(">>> Ready to process ALL scenes and send ALL renders. Proceed? (y/n): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("Aborted.")
        return

    total_processed = 0
    total_matches = len(matches)

    for scene_id, items in scenes.items():
        print(f"\nProcessing Scene ID: {scene_id} ({len(items)} items)")
        
        ancillary = get_scene_ancillary_data(session, scene_id, store_map)
        
        if not ancillary['json_content']:
            print(f"     [SKIP] Scene {scene_id} has no valid JSON.")
            total_processed += len(items)
            continue
        
        if not ancillary['store_id']:
            print(f"     [WARNING] No Store ID found for Scene {scene_id}.")

        print(f"     [GO] Sending {len(items)} render requests for Scene {scene_id}...")
        
        scene_processed = 0
        for item in items:
            send_render_request(session, item, ancillary)
            total_processed += 1
            scene_processed += 1
            print_progress(scene_processed, len(items), prefix="Sending", suffix=f"Total: {total_processed}/{total_matches}")

def main():
    with requests.Session() as s:
        s.headers.update(DEFAULT_HEADERS)
        while True:
            print_header("CONFIGURATOR TOOLBOX")
            print(f" ID: {CONFIGURATOR_ID} | Search: {TEXTURE_SEARCH_TERMS}")
            print(f" Target: {'ALL Scenes' if not SCENE_ID_LIST else f'{len(SCENE_ID_LIST)} Specific Scenes'}")
            print(f" Option Filter: {SCENE_OPTION_ID_LIST}")
            print("-" * 60)
            print(" 1. Patch Texture Properties")
            print(" 2. Send Renders (Matches enabled items only)")
            print(" 3. Re-Render Status Items (Only Failed/Status:3)")
            print(" 0. Exit")
            
            c = input("\n Choice > ").strip()
            if c == '0': break
            
            # --- OPTION 3: Re-Render Status Logic ---
            if c == '3':
                run_send_failed_logic(s, [])
                continue
            
            # --- OPTION 1 & 2: Existing Texture Logic ---
            if c in ['1', '2']:
                raw_data = fetch_target_textures(s)
                if not raw_data: 
                    print("No textures found.")
                    continue
                
                only_enabled_flag = True if c == '2' else False
                matches = filter_matches(raw_data, TEXTURE_SEARCH_TERMS, require_enabled=only_enabled_flag)
                
                if not matches:
                    print("No matches found (Note: Renders only match enabled items).")
                    continue
                
                if c == '1': run_patch_logic(s, matches)
                if c == '2': run_render_logic(s, matches)

if __name__ == "__main__":
    main()
