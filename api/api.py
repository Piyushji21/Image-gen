from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
import time
import json
from typing import Optional

app = FastAPI(title="Prompt2Photo")

# ====================== Kie AI Client ======================
API_KEY = "084521aaffe2f93d0dde3b72c7c4e08e"
BASE_URL = "https://api.kie.ai/api/v1"
UPLOAD_URL = "https://kieai.redpandaai.co/api/file-base64-upload"

class KieAIClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

    def create_task(self, prompt: str, aspect_ratio: str = "1:1"):
        payload = {
            "model": "grok-imagine/text-to-image",
            "input": {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio
            },
            "callBackUrl": "https://mzpcoieakbomhtvxgftl.supabase.co/functions/v1/kie-callback?secret=kie_cb_2026"
        }

        try:
            r = requests.post(f"{BASE_URL}/jobs/createTask", json=payload, headers=self.headers, timeout=20)
            r.raise_for_status()
            data = r.json()
            if data.get("code") == 200:
                return data.get("data", {}).get("taskId")
        except:
            pass
        return None

    def poll_task(self, task_id: str):
        start = time.time()
        while time.time() - start < 180:
            try:
                r = requests.get(f"{BASE_URL}/jobs/recordInfo", 
                               params={"taskId": task_id}, 
                               headers=self.headers, timeout=20)
                data = r.json()
                if data.get("code") == 200:
                    state = data.get("data", {}).get("state")
                    if state == "success":
                        result_str = data.get("data", {}).get("resultJson", "{}")
                        try:
                            result = json.loads(result_str)
                            urls = result.get("resultUrls") or result.get("result_urls") or []
                            return urls[0] if urls else None
                        except:
                            return None
            except:
                pass
            time.sleep(5)
        return None

client = KieAIClient()

# ====================== Web Pages ======================
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/generate")
async def generate(prompt: str = Form(...)):
    if not prompt or len(prompt.strip()) < 2:
        return JSONResponse({"error": "Please enter a valid prompt"}, status_code=400)

    task_id = client.create_task(prompt.strip())
    if not task_id:
        return JSONResponse({"error": "Failed to create generation task"}, status_code=500)

    image_url = client.poll_task(task_id)
    
    if image_url:
        return JSONResponse({
            "success": True,
            "image_url": image_url,
            "prompt": prompt
        })
    else:
        return JSONResponse({"error": "Generation timed out or failed"}, status_code=500)

# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
