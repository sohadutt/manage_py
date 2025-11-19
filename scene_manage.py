import requests
import sys
import urllib.parse
import json
import time
from typing import List, Dict, Any, Optional

BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzYzNjE3NDg2LCJpYXQiOjE3NjM1MzEwODYsImp0aSI6ImFlMTI5ZmI5MTM1ZTQ2MmZiNzVkNmFhODM1YjUxYzIxIiwidXNlcl9pZCI6MTA3NDEsIm1lbWJlciI6MTE1NTgsIm9yZ2FuaXphdGlvbiI6MjI5NywiaXNfZW1haWxfdmVyaWZpZWQiOnRydWUsImFwcF90eXBlIjoiYmFzZSJ9.UzgMx7gAZBqVo5gAfCbSm6GYUmJTKl1TtxASPiPmYrk"
CONFIGURATOR_ID = "7049"

REQUEST_DELAY = 0.5

# If empty, script will fetch ALL scenes.
SCENE_ID_LIST = [] 
SCENE_OPTION_ID_LIST = ["48988"]
TEXTURE_SEARCH_TERMS = ["Navy Blue"]

SCENE_DATA_URL = f"https://prod.imagine.io/configurator/api/v2/config-scene/?configurator={CONFIGURATOR_ID}&page=1"
PATCH_SCENE_TEXTURE_URL = "https://prod.imagine.io/configurator/api/v2/scene-texture/"

DEFAULT_HEADERS = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "accept-encoding": "gzip, deflate, br",
    "connection": "keep-alive",
    "accept": "application/json",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0"
}

def get_paginated_data(session: requests.Session, start_url: str) -> List[Dict[str, Any]]:
    all_results = []
    current_url = start_url
    base_url = start_url.split('?')[0]
    print(f"Starting data fetch from: {base_url}")

    total_items = 0
    items_fetched = 0
    is_first_page = True
    page_number = 1

    try:
        parsed_url = urllib.parse.urlparse(start_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        if 'page' in query_params:
            page_number = int(query_params['page'][0])
    except (ValueError, IndexError):
        page_number = 1

    while current_url:
        # --- THROTTLE: Wait before making the request ---
        time.sleep(REQUEST_DELAY)
        
        retries = 3
        delay = 1
        response = None
        
        while retries > 0:
            try:
                response = session.get(current_url)
                response.raise_for_status()
                break 
            except requests.exceptions.HTTPError as http_err:
                retries -= 1
                if response is not None and response.status_code in [500, 502, 503, 504]:
                    print(f"\nServer error ({http_err}). Retrying in {delay}s... ({retries} retries left)")
                    time.sleep(delay)
                    delay *= 2 
                else:
                    print(f"\nHTTP error occurred: {http_err}")
                    if response is not None and response.status_code in [401, 403]:
                        print("\n--- CRITICAL ERROR ---")
                        print("Token might be expired or invalid. Please update BEARER_TOKEN.")
                    current_url = None
                    break
            except requests.exceptions.RequestException as err:
                retries -= 1
                print(f"\nA request error occurred: {err}. Retrying in {delay}s... ({retries} retries left)")
                time.sleep(delay)
                delay *= 2
        
        if not current_url:
            break

        if retries == 0 and (response is None or (response is not None and response.status_code >= 500)):
            print(f"Failed to fetch {current_url} after multiple retries. Skipping this URL.")
            break

        if response is None:
            print(f"\nNo response received for {current_url}. Skipping.")
            break

        try:
            data = response.json()
        except json.JSONDecodeError:
            print(f"\nFailed to decode JSON from {current_url}. Skipping.")
            break

        page_results = data.get("results", [])
        
        if is_first_page:
            total_items = data.get("count", 0)
            is_first_page = False
            if not page_results and not total_items:
                print("No results found.")
                break
            if not total_items and page_results:
                print("Total item count not available. Progress bar will not be shown.")
        
        if page_results:
            all_results.extend(page_results)
            items_fetched += len(page_results)
            
            if total_items > 0:
                percentage = (items_fetched / total_items) * 100
                bar_length = 40
                filled_length = int(bar_length * items_fetched // total_items)
                bar = '█' * filled_length + '-' * (bar_length - filled_length)
                sys.stdout.write(f'\rProgress: |{bar}| {items_fetched}/{total_items} ({percentage:.1f}%)')
                sys.stdout.flush()
            else:
                print(f"Fetched page with {len(page_results)} results (Total: {items_fetched})")
        
        next_link = data.get("next_link")
        if next_link:
            current_url = next_link
            try:
                parsed_link = urllib.parse.urlparse(next_link)
                query_params = urllib.parse.parse_qs(parsed_link.query)
                if 'page' in query_params:
                    page_number = int(query_params['page'][0])
            except (ValueError, IndexError):
                pass 
        
        elif items_fetched < total_items and total_items > 0:
            if total_items > 0:
                sys.stdout.write('\n')
                sys.stdout.flush()
            print("No 'next_link' found, manually incrementing page...")
            
            page_number += 1
            
            parsed_start_url = urllib.parse.urlparse(start_url)
            query_params = urllib.parse.parse_qs(parsed_start_url.query)
            query_params['page'] = [str(page_number)]
            new_query = urllib.parse.urlencode(query_params, doseq=True)
            current_url = urllib.parse.urlunparse(parsed_start_url._replace(query=new_query))
            print(f"Fetching next page: {page_number}")
        else:
            current_url = None

    if total_items > 0:
        sys.stdout.write('\n')
        sys.stdout.flush()

    print(f"Fetch complete. Total items fetched: {len(all_results)}")
    return all_results

def patch_scene_texture(
    session: requests.Session, 
    texture_id: str, 
    data_id: Optional[str], 
    field_name: str, 
    field_value: bool, 
    item_name: str, 
    scene_id: Optional[str], 
    configurator_id: str
) -> bool:
    
    url = f"{PATCH_SCENE_TEXTURE_URL}{texture_id}/"

    # --- CONSTRUCT MULTIPART FORM DATA ---
    
    # 1. Prepare the nested 'data' JSON object
    # Use the field_name variable to set either 'is_enable' or 'is_updated' dynamically
    nested_json_data = {
        "id": int(data_id) if data_id and data_id.isdigit() else None,
        "scene_id": int(scene_id) if scene_id and scene_id.isdigit() else None,
        field_name: field_value
    }

    multipart_data = {
        'id': (None, str(texture_id)),
        'configurator': (None, str(configurator_id)),
        field_name: (None, 'true' if field_value else 'false'),
        'data': (None, json.dumps(nested_json_data))
    }

    try:
        response = session.patch(url, files=multipart_data)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"\n  [ERROR] Failed to update '{field_name}' for '{item_name}' (ID: {texture_id}): {e}")
        if hasattr(e, 'response') and e.response is not None:
             print(f"     Response: {e.response.text}")
        return False

def process_and_patch_textures(
    session: requests.Session, 
    all_items: List[Dict[str, Any]], 
    search_terms_list: List[str], 
    target_field: str,
    target_value: bool
):
    if not all_items:
        print("No data to process.")
        return
        
    if not search_terms_list:
        print("No search terms provided. Skipping patch process.")
        return
    
    lower_to_original_term = {term.lower(): term for term in search_terms_list}
    search_terms_lower_set = set(lower_to_original_term.keys())

    print(f"\nFiltering {len(all_items)} items for matches...")
    
    matches_to_patch = []
    for item in all_items:
        item_display_name = item.get("display_name", "")
        item_display_name_lower = item_display_name.lower()
        
        if item_display_name_lower in search_terms_lower_set:
            match_data = {
                "display_name": item_display_name,
                "id": str(item.get("id")),
                "data_id": str(item.get("data", {}).get("id")) if item.get("data") else None,
                "scene_id": str(item.get("fetched_for_scene_id")) if item.get("fetched_for_scene_id") else None
            }
            matches_to_patch.append(match_data)

    if not matches_to_patch:
        print(f"No exact matches found for terms: {search_terms_list}")
        return

    print(f"Found {len(matches_to_patch)} texture(s) to patch.")

    value_display = "true" if target_value else "false"
    confirm = input(f"Are you sure you want to set '{target_field}={value_display}' for these items? (y/n): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("Operation cancelled.")
        return

    patched_count = 0
    total = len(matches_to_patch)
    
    print(f"\n--- Starting Patch Operation ---")
    for i, item in enumerate(matches_to_patch, 1):
        print(f"[{i}/{total}] Updating {target_field} for '{item['display_name']}' (ID: {item['id']})...", end="", flush=True)
        
        time.sleep(REQUEST_DELAY)
        
        success = patch_scene_texture(
            session, 
            item['id'], 
            item['data_id'], 
            target_field,
            target_value, 
            item['display_name'],
            item['scene_id'],
            CONFIGURATOR_ID
        )
        
        if success:
            print(" Done.")
            patched_count += 1
        else:
            print(" Failed.")
            
    print(f"\n--- Patching Complete ---")
    print(f"Successfully Updated: {patched_count}/{total}")

def main():
    if "YOUR_BEARER_TOKEN" in BEARER_TOKEN:
        print("ERROR: Please replace 'YOUR_BEARER_TOKEN' in the script with your actual Bearer Token.")
        sys.exit(1)

    with requests.Session() as session:
        session.headers.update(DEFAULT_HEADERS)
        
        print("\n--- Scene Texture Patcher ---")
        print(f"Configurator ID: {CONFIGURATOR_ID}")
        print(f"Target Scenes: {SCENE_ID_LIST if SCENE_ID_LIST else 'ALL Scenes'}")
        print(f"Target Options: {SCENE_OPTION_ID_LIST if SCENE_OPTION_ID_LIST else 'All Options'}")
        print(f"Search Terms: {TEXTURE_SEARCH_TERMS}")
        print(f"Request Delay: {REQUEST_DELAY}s")
        
        print("\nSelect the field you want to update:")
        print("1. is_enable")
        print("2. is_updated")
        
        field_choice = input("Enter choice (1 or 2): ").strip()
        target_field = ""
        
        if field_choice == '1':
            target_field = "is_enable"
        elif field_choice == '2':
            target_field = "is_updated"
        else:
            print("Invalid choice. Exiting.")
            sys.exit(1)
            
        value_input = input(f"Set '{target_field}' to True or False? (t/f): ").strip().lower()
        target_value = None
        
        if value_input in ['t', 'true', '1', 'yes', 'y']:
            target_value = True
        elif value_input in ['f', 'false', '0', 'no', 'n']:
            target_value = False
        else:
            print("Invalid input. Exiting.")
            sys.exit(1)

        # --- Fetch Scene IDs if SCENE_ID_LIST is empty ---
        target_scene_ids = SCENE_ID_LIST
        if not target_scene_ids:
            print("\nSCENE_ID_LIST is empty. Fetching ALL scene IDs for the configurator...")
            all_scenes_data = get_paginated_data(session, SCENE_DATA_URL)
            target_scene_ids = [str(item.get('id')) for item in all_scenes_data if item.get('id')]
            print(f"Found {len(target_scene_ids)} scenes.")
            
            if not target_scene_ids:
                print("No scenes found. Exiting.")
                return

        combined_texture_data = []
        print(f"\nStarting batch fetch for {len(target_scene_ids)} scenes...")
        
        total_fetches = len(target_scene_ids) * (len(SCENE_OPTION_ID_LIST) if SCENE_OPTION_ID_LIST else 1)
        current_fetch = 0
        
        for scene_id in target_scene_ids:
            if not SCENE_OPTION_ID_LIST:
                current_fetch += 1
                print(f"Fetching {current_fetch}/{total_fetches}: scene={scene_id} (all options)...")
                current_url = f"https://prod.imagine.io/configurator/api/v2/scene-texture/?scene={scene_id}&sort=name&per_page=50"
                data = get_paginated_data(session, current_url)
                for item in data:
                    item['fetched_for_scene_id'] = scene_id
                combined_texture_data.extend(data)
            else:
                for option_id in SCENE_OPTION_ID_LIST:
                    current_fetch += 1
                    print(f"Fetching {current_fetch}/{total_fetches}: scene={scene_id}, option={option_id}...")
                    current_url = f"https://prod.imagine.io/configurator/api/v2/scene-texture/?scene={scene_id}&sceneoption={option_id}&sort=name&per_page=50"
                    data = get_paginated_data(session, current_url)
                    for item in data:
                        item['fetched_for_scene_id'] = scene_id
                    combined_texture_data.extend(data)
        
        if combined_texture_data:
            process_and_patch_textures(session, combined_texture_data, TEXTURE_SEARCH_TERMS, target_field, target_value)
        else:
            print("No texture data found to process.")

if __name__ == "__main__":
    main()