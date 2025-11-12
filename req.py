import requests

url = "https://api.clickup.com/api/v2/task/"
task_id = "86du95w97"

main_url = url + task_id

headers = {
    "accept": "application/json",
    "Authorization": "pk_89184167_X7ANWA9U7KYGGHVFZWHPZPEZM5SI5E3S"
}

response = requests.get(main_url, headers=headers)

print(response.text)