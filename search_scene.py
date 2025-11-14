import requests
import sys
import urllib.parse
import json
import os
import shutil
import zipfile
import time
from typing import List, Dict, Any, Optional

BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzYzMTgwMzE3LCJpYXQiOjE3NjMwOTM5MTcsImp0aSI6Ijg4Y2VmNjIzNTllMTQ3NjZhZTdlNTVmZmQyZDM4ZGYyIiwidXNlcl9pZCI6NjYyMiwibWVtYmVyIjoxMDc4MSwib3JnYW5pemF0aW9uIjo3MzY5LCJpc19lbWFpbF92ZXJpZmllZCI6dHJ1ZSwiYXBwX3R5cGUiOiJiYXNlIn0.yRwCb3wjYt6llJ9GGHBUqm0HxeZXfyARD_8XouW1VCQ"
CONFIGURATOR_ID = "4807"

SCENE_DATA_URL = f"https://prod.imagine.io/configurator/api/v2/config-scene/?configurator={CONFIGURATOR_ID}&page=1"

SCENE_ID_LIST = ["20805"]
SCENE_OPTION_ID_LIST = ["39931"]
TEXTURE_SEARCH_TERMS = ["White"]

PUBLIC_TOKEN = "de6627c1-de02-3225-8d83-e06ceae99b4c"
RENDER_DOWNLOAD_API_URL = "https://prod.imagine.io/configurator/api/v2/configurator-images-download/"
CONFIG_PUBLIC_DATA_URL = f"https://prod.imagine.io/configurator/api/v2/v3/config-public-data/{CONFIGURATOR_ID}/?is_render=true&page=1"

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

def _process_scene_products(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    products = []
    scene_id = str(item.get("id"))
    scene_name = item.get("name", "")
    sceneproduct_list = item.get("sceneproduct_data", [])

    if not (sceneproduct_list and isinstance(sceneproduct_list, list)):
        return []

    for idx, product_data in enumerate(sceneproduct_list):
        if isinstance(product_data, dict):
            products.append({
                "scene_id": scene_id,
                "scene_name": scene_name,
                "sceneproduct_num": idx,
                "sceneproduct_data_name": product_data.get("name", ""),
                "sceneproduct_data_product_id": str(product_data.get("product", "")) if product_data.get("product") else None
            })
    return products

def search_public_scenes(all_items: List[Dict[str, Any]]):
    if not all_items:
        print("No data to search.")
        return
    try:
        search_term = input("Enter a search term for 'name' (or '*' for all): ").strip()
    except EOFError:
        print("No input received. Aborting search.")
        return
        
    if not search_term:
        print("No search term entered.")
        return
    
    matches_store = []
    search_term_lower = search_term.lower()
    
    print(f"Searching for scenes where name contains '{search_term}'...")

    for item in all_items:
        item_name = item.get("name", "")
        
        if search_term == '*' or search_term_lower in item_name.lower():
            matches_store.extend(_process_scene_products(item))

    if not matches_store:
        print(f"--- No matches found for '{search_term}' ---")
    else:
        print(f"\n--- Found {len(matches_store)} match(es) for '{search_term}' ---\n")
        print(json.dumps(matches_store, indent=4))

def search_scene_textures(all_items: List[Dict[str, Any]], search_terms_list: List[str]):
    if not all_items:
        print("No data was fetched. Cannot perform search.")
        return
        
    if not search_terms_list:
        print("No search terms provided, returning all fetched texture data...")
        all_texture_data = []
        for item in all_items:
            item_tiling_value_x = item.get("material_properties", {}).get("tilingOffsetValue", {}).get("_MainTex", {}).get("xMatTiling", None)
            item_tiling_value_y = item.get("material_properties", {}).get("tilingOffsetValue", {}).get("_MainTex", {}).get("yMatTiling", None)
            match_data = {
                "display_name": item.get("display_name", ""),
                "id": str(item.get("id")),
                "data_id": str(item.get("data", {}).get("id")) if item.get("data") else None,
                "sceneoption": str(item.get("sceneoption")) if item.get("sceneoption") else None,
                "scene_id": str(item.get("fetched_for_scene_id")) if item.get("fetched_for_scene_id") else None,
                # "tiling": [f"x: {item_tiling_value_x}", f"y: {item_tiling_value_y}"] if item_tiling_value_x is not None and item_tiling_value_y is not None else None
            }
            all_texture_data.append(match_data)
        
        print(f"\n--- Found {len(all_texture_data)} total texture items ---")
        print("--- JSON Output ---")
        print(json.dumps(all_texture_data, indent=4))
        return

    lower_to_original_term = {term.lower(): term for term in search_terms_list}
    search_terms_lower_set = set(lower_to_original_term.keys())

    results_json = {term: [] for term in search_terms_list}
    total_matches_found = 0

    print(f"Processing {len(all_items)} items against {len(search_terms_list)} search terms (exact match)...")

    for item in all_items:
        item_display_name = item.get("display_name", "")
        item_display_name_lower = item_display_name.lower()
        item_tiling_value_x = item.get("material_properties", {}).get("tilingOffsetValue", {}).get("_MainTex", {}).get("xMatTiling", None)
        item_tiling_value_y = item.get("material_properties", {}).get("tilingOffsetValue", {}).get("_MainTex", {}).get("yMatTiling", None)
        
        if item_display_name_lower in search_terms_lower_set:
            match_data = {
                "display_name": item_display_name,
                "id": str(item.get("id")),
                "data_id": str(item.get("data", {}).get("id")) if item.get("data") else None,
                "sceneoption": str(item.get("sceneoption")) if item.get("sceneoption") else None,
                "scene_id": str(item.get("fetched_for_scene_id")) if item.get("fetched_for_scene_id") else None,
                # "tiling": [f"x: {item_tiling_value_x}", f"y: {item_tiling_value_y}"] if item_tiling_value_x is not None and item_tiling_value_y is not None else None
            }
            original_term = lower_to_original_term[item_display_name_lower]
            results_json[original_term].append(match_data)
            total_matches_found += 1

    print(f"\n--- Total matches found across all terms: {total_matches_found} ---")
    print("--- JSON Output ---")
    print(json.dumps(results_json, indent=4))

def search_public_data_store_id(all_items: List[Dict[str, Any]]) -> List[str]:
    if not all_items:
        print("No data to search.")
        return []
    try:
        store_ids = []
        for item in all_items:
            store_id = item.get("id")
            if store_id:
                store_ids.append(str(store_id))
        return store_ids
    except EOFError:
        print("No input received. Aborting search.")
        return []

def search_public_data_render_id(all_items: List[Dict[str, Any]], search_terms_list: List[str]) -> Dict[str, Dict[str, str]]:
    if not all_items:
        print("No data to search.")
        return {}
    try:
        render_id_to_details_map = {}
        
        if not search_terms_list:
            print("No search terms. Getting all render IDs...")
            for item in all_items:
                render_id = item.get("render_id")
                store_id = item.get("fetched_for_store_id")
                display_name = item.get("display_name", f"render_{render_id}")
                if render_id and store_id:
                    render_id_to_details_map[str(render_id)] = {"store_id": str(store_id), "display_name": display_name}
        else:
            print(f"Filtering renders by {len(search_terms_list)} search terms (relative match)...")
            
            for item in all_items:
                item_display_name_lower = item.get("display_name", "").lower()
                for term in search_terms_list:
                    if term.lower() in item_display_name_lower: # <-- This is a RELATIVE match
                        render_id = item.get("render_id")
                        store_id = item.get("fetched_for_store_id")
                        display_name = item.get("display_name", f"render_{render_id}")
                        if render_id and store_id:
                            render_id_to_details_map[str(render_id)] = {"store_id": str(store_id), "display_name": display_name}
                        break # Item matched, move to next item
                        
        print(f"Found {len(render_id_to_details_map)} unique render IDs to download.")
        return render_id_to_details_map
        
    except EOFError:
        print("No input received. Aborting search.")
        return {}

def download_renders(session: requests.Session, render_map: Dict[str, Dict[str, str]]):
    if not render_map:
        print("No render IDs provided to download.")
        return

    print(f"--- Starting download for {len(render_map)} renders ---")
    dump_folder = "dump"
    os.makedirs(dump_folder, exist_ok=True)
    print(f"Files will be saved to '{os.path.abspath(dump_folder)}'")

    for render_id, details in render_map.items():
        if not render_id or render_id == 'None':
            continue
            
        store_id = str(details.get("store_id", ""))
        display_name = details.get("display_name", f"render_{render_id}")
        
        # Sanitize display_name to make it a valid folder name
        safe_display_name = "".join(c for c in display_name if c.isalnum() or c in (' ', '_')).rstrip()
        if not safe_display_name: # Handle empty or invalid names
            safe_display_name = f"render_{render_id}"

        print(f"\nFetching download link for render_id: {render_id} (Store: {store_id}, Name: {safe_display_name})")
        api_url = f"{RENDER_DOWNLOAD_API_URL}{render_id}/"
        
        # New folder structure: dump/<store_id>/<safe_display_name>/<render_id>.zip
        store_folder = os.path.join(dump_folder, store_id)
        extract_path = os.path.join(store_folder, safe_display_name) # e.g., dump/11245/Primed White/
        filepath = os.path.join(extract_path, f"{render_id}.zip") # Put the zip inside the final folder
        
        os.makedirs(extract_path, exist_ok=True)
        
        try:
            # 1. Get the Download URL
            response = session.get(api_url)
            response.raise_for_status()
            data = response.json()
            zip_url = data.get("data", {}).get("zip_file")

            if not zip_url:
                print(f"  No 'zip_file' URL found in API response for {render_id}")
                continue

            # 2. Download with Progress Bar
            print(f"  Downloading from: {zip_url[:70]}...")
            with session.get(zip_url, stream=True) as r_zip:
                r_zip.raise_for_status()
                
                total_size = int(r_zip.headers.get('content-length', 0))
                downloaded_size = 0
                chunk_size = 8192 # 8KB

                with open(filepath, 'wb') as f_out:
                    for chunk in r_zip.iter_content(chunk_size=chunk_size):
                        f_out.write(chunk)
                        downloaded_size += len(chunk)
                        
                        if total_size > 0:
                            percentage = (downloaded_size / total_size) * 100
                            bar_length = 40
                            filled_length = int(bar_length * downloaded_size // total_size)
                            bar = '█' * filled_length + '-' * (bar_length - filled_length)
                            sys.stdout.write(f'\r  Progress: |{bar}| {downloaded_size/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB ({percentage:.1f}%)')
                            sys.stdout.flush()
                        else:
                            sys.stdout.write(f'\r  Downloaded: {downloaded_size/1024/1024:.1f}MB')
                            sys.stdout.flush()
            
            sys.stdout.write('\n')
            print(f"  Download complete: {filepath}")

            # 3. Extract the zip file
            print(f"  Extracting...")
            try:
                with zipfile.ZipFile(filepath, 'r') as zip_ref:
                    # os.makedirs(extract_path, exist_ok=True) # Already created
                    zip_ref.extractall(extract_path)
                print(f"  Successfully extracted to: {extract_path}")

                # 4. Delete the zip file
                try:
                    os.remove(filepath)
                    print(f"  Deleted zip file: {filepath}")
                except OSError as e:
                    print(f"  Error deleting zip file {filepath}: {e}")

            except zipfile.BadZipFile as e:
                print(f"  Error: Failed to extract {filepath}. File may be corrupt. {e}")
            except Exception as e:
                print(f"  An error occurred during extraction: {e}")

        except requests.exceptions.RequestException as e:
            print(f"  Failed to download {render_id}: {e}")

def main():
    if "YOUR_BEARER_TOKEN" in BEARER_TOKEN:
        print("ERROR: Please replace 'YOUR_BEARER_TOKEN' in the script with your actual Bearer Token.")
        sys.exit(1)

    with requests.Session() as session:
        session.headers.update(DEFAULT_HEADERS)
        
        while True:
            print("\n--- API Search Menu ---")
            print("1. Search Public Scenes (by 'name')")
            print("2. Search Scene Textures (by 'display_name')")
            print("3. Search & Download Public Renders")
            print("0. Exit")

            choice = input("Enter your choice (1, 2, 3, or 0): ").strip()

            if choice == '1':
                all_data = get_paginated_data(session, SCENE_DATA_URL)
                if all_data:
                    search_public_scenes(all_data)
                    
            elif choice == '2':
                combined_texture_data = []
                print(f"Starting batch fetch for {len(SCENE_ID_LIST)} scenes...")
                
                total_fetches = len(SCENE_ID_LIST) * (len(SCENE_OPTION_ID_LIST) if SCENE_OPTION_ID_LIST else 1)
                current_fetch = 0
                
                for scene_id in SCENE_ID_LIST:
                    if not SCENE_OPTION_ID_LIST:
                        # Fetch all options for the scene
                        current_fetch += 1
                        print(f"\n--- Fetching {current_fetch}/{total_fetches}: scene={scene_id} (all options) ---")
                        current_url = f"https://prod.imagine.io/configurator/api/v2/scene-texture/?scene={scene_id}&sort=name&per_page=50"
                        data = get_paginated_data(session, current_url)
                        for item in data:
                            item['fetched_for_scene_id'] = scene_id
                        combined_texture_data.extend(data)
                    else:
                        # Fetch only specified options
                        for option_id in SCENE_OPTION_ID_LIST:
                            current_fetch += 1
                            print(f"\n--- Fetching {current_fetch}/{total_fetches}: scene={scene_id}, sceneoption={option_id} ---")
                            current_url = f"https://prod.imagine.io/configurator/api/v2/scene-texture/?scene={scene_id}&sceneoption={option_id}&sort=name&per_page=50"
                            data = get_paginated_data(session, current_url)
                            for item in data:
                                item['fetched_for_scene_id'] = scene_id
                            combined_texture_data.extend(data)
                
                print(f"\nBatch fetch complete. Total items from all scenes/options: {len(combined_texture_data)}")
                if combined_texture_data:
                    search_scene_textures(combined_texture_data, TEXTURE_SEARCH_TERMS)
                    
            elif choice == '3':
                print("--- Fetching Public Config Data (to get Store IDs) ---")
                all_data = get_paginated_data(session, CONFIG_PUBLIC_DATA_URL)
                all_texture_data = []
                
                if not all_data:
                    print("No public config data found.")
                    continue

                store_ids = search_public_data_store_id(all_data)
                if not store_ids:
                    print("No store_ids found, skipping public texture fetch.")
                    continue
                
                print(f"Found {len(store_ids)} store(s). Fetching textures...")
                
                total_fetches = len(store_ids) * (len(SCENE_OPTION_ID_LIST) if SCENE_OPTION_ID_LIST else 1)
                current_fetch = 0

                for store in store_ids:
                    if not SCENE_OPTION_ID_LIST:
                        # Fetch all options for the store
                        current_fetch += 1
                        print(f"\n--- Fetching {current_fetch}/{total_fetches}: store={store} (all options) ---")
                        public_texture_url = f"httpss://prod.imagine.io/configurator/api/v2/scenetexture-public-data/?token={PUBLIC_TOKEN}&store_id={store}&is_public=false&page=1"
                        texture_data = get_paginated_data(session, public_texture_url)
                        for item in texture_data:
                            item['fetched_for_store_id'] = store
                        all_texture_data.extend(texture_data)
                    else:
                        # Fetch only specified options
                        for option_id in SCENE_OPTION_ID_LIST:
                            current_fetch += 1
                            print(f"\n--- Fetching {current_fetch}/{total_fetches}: store={store}, sceneoption={option_id} ---")
                            public_texture_url = f"httpss://prod.imagine.io/configurator/api/v2/scenetexture-public-data/?token={PUBLIC_TOKEN}&store_id={store}&sceneoption_id={option_id}&is_public=false&page=1"
                            texture_data = get_paginated_data(session, public_texture_url)
                            for item in texture_data:
                                item['fetched_for_store_id'] = store
                            all_texture_data.extend(texture_data)
                
                print(f"\nBatch texture fetch complete. Total items: {len(all_texture_data)}")

                if all_texture_data:
                    render_map = search_public_data_render_id(all_texture_data, TEXTURE_SEARCH_TERMS)
                    if render_map:
                        download_renders(session, render_map)
                    else:
                        print(f"No render_ids found for the search terms: {TEXTURE_SEARCH_TERMS}")
                else:
                    print("No public texture data found.")
                        
            elif choice == '0':
                print("Exiting.")
                break
                
            else:
                print("Invalid choice. Please enter 1, 2, 3, or 0.")

if __name__ == "__main__":
    main()
