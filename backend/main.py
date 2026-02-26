from dotenv import load_dotenv
from supabase import create_client, Client
import os 
import requests

load_dotenv()

def get_merimee():
    supabase: Client = create_client(
        os.environ.get("SUPABASE_URL"),
        os.environ.get("SUPABASE_SECRET_KEY")
    )

    base_url = "https://tabular-api.data.gouv.fr/api/resources/3a52af4a-f9da-4dcc-8110-b07774dfb3bc/data/"
    page = 1

    while True:
        print("Fetching page:", page)
        url = f"{base_url}?page={page}&page_size=200"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()

            # Check if there are items in the current page
            if not data.get('data') or len(data['data']) == 0:
                break
            for item in data['data']:
                    for key in list(item.keys()):
                        if key == "__id":
                            del item[key]
                        else:
                            item[key.lower()] = item.pop(key)
            supabase.table('merimee_buildings').insert(data['data']).execute()    
            page += 1
        else:
            print(f"Erreur {response.status_code}: {response.text}")
            break

if __name__ == "__main__":
    get_merimee()
