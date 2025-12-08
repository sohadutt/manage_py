import requests
import sys
import urllib.parse
import json
import time
import os
import gzip
import io
import lzma
import bz2
import zlib
from datetime import datetime
from typing import List, Dict, Any, Optional

# --- OPTIONAL IMPORTS ---
try:
    import brotli
except ImportError:
    brotli = None

try:
    import zstandard as zstd
except ImportError:
    zstd = None

# --- CONFIGURATION ---
BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzY1MjYzODQzLCJpYXQiOjE3NjUxNzc0MzksImp0aSI6IjUzZWE3ZmM5YjhmMzQxMDk4YTUyMTA4YWEzNTNlMGFkIiwidXNlcl9pZCI6MTA3NDEsIm1lbWJlciI6MTE1NTgsIm9yZ2FuaXphdGlvbiI6MjI5NywiaXNfZW1haWxfdmVyaWZpZWQiOnRydWUsImFwcF90eXBlIjoiYmFzZSJ9.g3i3-OxfHrdo9-X1HGiUaqd_B1aWrFij9m0x1ee2dO4"
CONFIGURATOR_ID = "7060"

SCENE_ID_LIST = [] 
SCENE_OPTION_ID_LIST = ["49971"] 
TEXTURE_SEARCH_TERMS = ["Matte White"] 

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
    "accept-encoding": "gzip, deflate", 
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
    if total == 0:
        return
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    if iteration == total:
        sys.stdout.write('\n')
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
    
    try:
        init_resp = session.get(current_url)
        init_resp.raise_for_status()
        data = init_resp.json()
        total_count = data.get("count", 0)
        all_results.extend(data.get("results", []))
        current_url = data.get("next_link")
    except requests.exceptions.HTTPError:
        log_error(init_resp, "Fetching Data List") 
        current_url = None
    except Exception as e:
        print(f" [!] Network Error: {e}")
        current_url = None

    if total_count == 0:
        return all_results

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
    try: return lzma.decompress(raw_bytes)
    except: pass
    try: return zlib.decompress(raw_bytes)
    except: pass
    try: return bz2.decompress(raw_bytes)
    except: pass
    return raw_bytes

def get_scene_ancillary_data(session: requests.Session, scene_id: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"json_content": None, "store_id": None, "sceneview_id": None, "local_path": None}
    
    print(f"   > Resolving details for Scene {scene_id}...")

    try:
        resp = session.get(DETAILS_URL.format(scene_id=scene_id))
        resp.raise_for_status()
        details = resp.json()
        result["store_id"] = str(details.get("store", "18340")) 
        
        json_url = details.get("json_file")

        if json_url:
            print("     [i] Downloading JSON file...")
            file_resp = session.get(json_url) 
            
            if file_resp.status_code != 200:
                log_error(file_resp, "Downloading JSON File")
                return result

            raw_content = file_resp.content
            final_json_obj = None

            try:
                final_json_obj = file_resp.json()
            except ValueError:
                decompressed_bytes = robust_decompress(raw_content)
                try:
                    final_json_obj = json.loads(decompressed_bytes)
                except Exception:
                    print(f"     [!] Parsing failed.")

            if final_json_obj is not None:
                clean_bytes = json.dumps(final_json_obj, indent=4).encode('utf-8')
                result["json_content"] = clean_bytes

                try:
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    save_dir = os.path.join("json_dump", today_str, CONFIGURATOR_ID, str(scene_id))
                    os.makedirs(save_dir, exist_ok=True)
                    
                    file_name = f"scene_{scene_id}.json"
                    file_path = os.path.join(save_dir, file_name)
                    
                    with open(file_path, 'wb') as f:
                        f.write(clean_bytes)
                    result["local_path"] = file_path
                except Exception as disk_err:
                    print(f"     [!] Error saving file to disk: {disk_err}")
    except Exception as e:
        print(f"     [!] Details Error: {e}")

    try:
        resp = session.get(VIEWS_URL.format(scene_id=scene_id))
        if resp.status_code == 200:
            views = resp.json().get("results", [])
            if views:
                result["sceneview_id"] = str(views[0].get("id"))
            else:
                result["sceneview_id"] = scene_id
        else:
             result["sceneview_id"] = scene_id
    except Exception:
        result["sceneview_id"] = scene_id

    return result

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
        log_error(r, f"Patching {field}")
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
        r = None
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
    except requests.exceptions.HTTPError:
        if r is not None: log_error(r, "Sending Render Request")
        return False
    except Exception as e:
        print(f"\n     [!] Render Error: {e}")
        return False

def fetch_target_textures(session):
    target_scenes = SCENE_ID_LIST
    if not target_scenes:
        print_header("Fetching All Configurator Scenes")
        scenes_data = get_paginated_data(session, SCENE_LIST_URL, "Scenes")
        target_scenes = [str(s['id']) for s in scenes_data]
        print(f"   > Total Scenes Found: {len(target_scenes)}")
    
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
                else:
                    log_error(r, "Fetching Textures")
            except Exception as e:
                pass
            print_progress(current_op, total_ops, prefix="Scanning", suffix=f"Found: {len(all_textures)}")
    return all_textures

def filter_matches(all_items, search_terms, require_enabled=False):
    matches = []
    filter_desc = search_terms if search_terms else 'All Items'
    if require_enabled:
        filter_desc = str(filter_desc) + " (Only Enabled)"    
    print_header(f"Filtering Results: {filter_desc}")
    
    search_lower = [t.lower() for t in search_terms] if search_terms else []

    for item in all_items:
        name = item.get("display_name", "").lower()
        has_name_match = True
        if search_lower:
            has_name_match = any(term in name for term in search_lower)
        is_enabled = item.get("data", {}).get("is_enable")
        has_enabled_match = True
        if require_enabled:
            if is_enabled is not True:
                has_enabled_match = False

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
    scenes = {}
    for m in matches:
        s_id = m['scene_id']
        if s_id not in scenes: scenes[s_id] = []
        scenes[s_id].append(m)
    
    print_header(f"Preparing {len(matches)} Textures across {len(scenes)} Scenes")
    
    total_processed = 0
    total_matches = len(matches)
    
    for scene_id, items in scenes.items():
        print(f"\nProcessing Scene ID: {scene_id} ({len(items)} items)")
        ancillary = get_scene_ancillary_data(session, scene_id)
        
        if not ancillary['json_content']:
            print(f"     [SKIP] Scene {scene_id} has no valid JSON.")
            total_processed += len(items)
            continue
        
        print(f"\nJSON parsed & saved for Scene {scene_id}.")
        print(f"Ready to send render requests for {len(items)} textures.")
        user_choice = input(">>> Do you want to SEND RENDERS for this scene? (y/n): ").strip().lower()

        if user_choice not in ['y', 'yes']:
            print(f"     [SKIP] Skipping render requests for Scene {scene_id}.")
            total_processed += len(items)
            continue

        print(f"     [GO] Sending {len(items)} requests...")
        scene_processed = 0
        for item in items:
            send_render_request(session, item, ancillary)
            total_processed += 1
            scene_processed += 1
            print_progress(scene_processed, len(items), prefix="Sending", suffix=f"Total: {total_processed}/{total_matches}")

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
            print(" 2. Send Renders (SKIPS DISABLED ITEMS)")
            print(" 0. Exit")
            
            c = input("\n Choice > ").strip()
            if c == '0': break
            
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
