import requests

def get_paginated_data(start_url, headers=None):
    payload = {}
    all_results = []
    current_url = start_url
    base_url = start_url.split('?')[0]
    print(f"Starting data fetch from: {base_url}")

    while current_url:
        try:
            response = requests.get(current_url, headers=headers, data=payload)
            response.raise_for_status()
            data = response.json()

            page_results = data.get("results", [])
            if page_results:
                all_results.extend(page_results)
                print(f"Fetched page with {len(page_results)} results")
            current_url = data.get("next_link")

        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
            if response.status_code in [401, 403]:
                print("\n--- CRITICAL ERROR ---")
                print("Token might be expired or invalid.")
            break
        except requests.exceptions.RequestException as err:
            print(f"An error occurred: {err}")
            break
    return all_results

def search_public_scenes(all_items):
    if not all_items:
        print("No data to search.")
        return
    try:
        search_term = input("Enter a search term for 'name': ").strip().lower()
    except EOFError:
        return
    if not search_term:
        print("No search term entered.")
        return

    matches = []
    for item in all_items:
        item_name = item.get("name", "")
        if search_term in item_name.lower():
            matches.append({
                "id": item.get("id"),
                "name": item_name
            })
    if not matches:
        print(f"--- No matches found for '{search_term}' ---")
    else:
        print(f"\n--- Found {len(matches)} match(es) for '{search_term}' ---\n")
        for match in matches:
            print(f"id: \"{match['id']}\", name: \"{match['name']}\"")

def search_scene_textures(all_items):
    if not all_items:
        print("No data was fetched. Cannot perform search.")
        return

    try:
        search_term = input("Enter a search term for 'texture-display_name': ").strip().lower()
    except EOFError:
        return
    if not search_term:
        print("No search term entered.")
        return
    matches = []
    for item in all_items:
        item_display_name = item.get("display_name", "")

        if search_term in item_display_name.lower():
            data_id = item.get("data", {}).get("id")
            matches.append({
                "display_name": item_display_name,
                "id": item.get("id"),
                "data_id": data_id,
                "sceneoption": item.get("sceneoption"),
                "scene_id": item.get("fetched_for_scene_id") # Get the scene_id we added
            })

    if not matches:
        print(f"--- No matches found for '{search_term}' ---")
    else:
        print(f"\n--- Found {len(matches)} match(es) for '{search_term}' ---\n")
        for match in matches:
            print(f"  display_name: \"{match['display_name']}\"")
            print(f"    scene_id: \"{match['scene_id']}\"") # Print the scene_id
            print(f"    id: \"{match['id']}\"")
            print(f"    data_id: \"{match['data_id']}\"")
            print(f"    sceneoption: \"{match['sceneoption']}\"\n")

if __name__ == "__main__":
    SCENE_DATA_URL = "http://prod.imagine.io/configurator/api/v2/all-scene-public-data/?token=39e211af-9a5f-3e03-b198-4f01bddc5c90&is_render=true&per_page=30&page=1"
    SCENE_ID = ["21137", "21138", "21139"]
    SCENE_OPTION_ID = ["47589", "47588", "47587"]
    BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzYyOTIxMTY4LCJpYXQiOjE3NjI3NDgyMjUsImp0aSI6IjYxMTAyMmE1M2U5NTRhNjVhYzVlZmEzZDRjZDIzMjFkIiwidXNlcl9pZCI6NjYyMiwibWVtYmVyIjoxNjU3Mywib3JnYW5pemF0aW9uIjoxMzU5MiwiaXNfZW1haWxfdmVyaWZpZWQiOnRydWUsImFwcF90eXBlIjoiYmFzZSJ9.ZWnChlM_h7vCyug0wByDRnpOgNEe86avKlNTZF3QYsE"

    TEXTURE_HEADERS = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "accept-encoding": "gzip, deflate, br",
        "connection": "keep-alive",
        "accept": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0"
    }

    while True:
        print("\n--- API Search Menu ---")
        print("1. Search Public Scenes (by 'name')")
        print("2. Search Scene Textures (by 'display_name') [Loops through all SCENE_OPTION_IDs]")
        print("0. Exit")

        choice = input("Enter your choice (1, 2, or 0): ").strip()

        if choice == '1':
            all_data = get_paginated_data(SCENE_DATA_URL, headers=None)
            if all_data:
                search_public_scenes(all_data)
        elif choice == '2':
            combined_texture_data = []
            print(f"Starting batch fetch for {len(SCENE_ID)} scenes and {len(SCENE_OPTION_ID)} scene options...")
            
            for scene_id in SCENE_ID:
                for option_id in SCENE_OPTION_ID:
                    print(f"\n--- Fetching for scene={scene_id}, sceneoption={option_id} ---")
                    current_url = f"https://prod.imagine.io/configurator/api/v2/scene-texture/?scene={scene_id}&sceneoption={option_id}&sort=name"
                    data = get_paginated_data(current_url, headers=TEXTURE_HEADERS)
                    
                    # Add the scene_id to each item before storing it
                    for item in data:
                        item['fetched_for_scene_id'] = scene_id
                        
                    combined_texture_data.extend(data)
            
            print(f"\nBatch fetch complete. Total items: {len(combined_texture_data)}")
            if combined_texture_data:
                search_scene_textures(combined_texture_data)
        elif choice == '0':
            print("Exiting.")
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 0.")