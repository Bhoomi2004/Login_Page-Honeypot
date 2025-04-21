import requests

url = "http://localhost:5000/login"

data = {
    "email": "botuser@example.com",
    "password": "botpassword",
    "honeypot": "IAmABot"  # This triggers the honeypot
}

# Simulate multiple bot requests
for i in range(1):
    response = requests.post(url, data=data)
    print(f"Attempt {i+1}: Status Code {response.status_code}")
