import requests
import time

# Replace these variables with your actual endpoint and API key
endpoint = '<<your instance>>.openai.azure.com'
api_key = '<<your key>>'

url = f"https://{endpoint}/openai/assistants?api-version=2024-05-01-preview"
headers = {
    'api-key': api_key,
    'Content-Type': 'application/json',
}
data = {
    "instructions": "python code creator dsafdasf",
      "name": "testrb",
  "tools": [],
  "model": "gpt-4",
  "tool_resources": {
    "code_interpreter": {
      "file_ids": [
        "assistant-s8grUFK2VIT08OyTfvXdFdJG",
      ]
    }
  },
  "temperature": 1,
  "top_p": 1
}

response = requests.post(url, headers=headers, json=data)
assistent_id = response.json().get("id")
print(assistent_id)

# Create a thread
create_thread_url = f"https://{endpoint}/openai/threads?api-version=2024-05-01-preview"
create_thread_response = requests.post(create_thread_url, headers=headers, data='{}')
thread_id = create_thread_response.json().get("id")  # Assuming the response contains an "id" field
print(thread_id)

# Add a user question to the thread
add_question_url = f"https://{endpoint}/openai/threads/{thread_id}/messages?api-version=2024-05-01-preview"
question_data = {
  "role": "user",
  "content": "give me python code to store data on adlsgen2"
}
add_question_response = requests.post(add_question_url, headers=headers, json=question_data)

# Run the thread
run_thread_url = f"https://{endpoint}/openai/threads/{thread_id}/runs?api-version=2024-05-01-preview"
run_data = {
    "assistant_id": assistent_id,  # Assuming this is a string, it should be quoted
}

run_thread_response = requests.post(run_thread_url, headers=headers, json=run_data)
run_id = run_thread_response.json().get("id")
print(run_id)

run_id_url = f"https://{endpoint}/openai/threads/{thread_id}/runs/{run_id}?api-version=2024-05-01-preview"
run_id_status = requests.get(run_id_url, headers=headers)
#print(run_id_status.json())

i=1
while run_id_status.json().get("status") in ['queued', 'in_progress', 'cancelling']:
    time.sleep(1)
    i= i + 1
    run_id_url = f"https://{endpoint}/openai/threads/{thread_id}/runs/{run_id}?api-version=2024-05-01-preview"
    run_id_status = requests.get(run_id_url, headers=headers)
    print(str(i) + ", " + str(run_id_status.json().get("status")))

response_thread_url = f"https://{endpoint}/openai/threads/{thread_id}/messages?api-version=2024-05-01-preview"
response_response= requests.get(response_thread_url, headers=headers)

print(response_response.json())
