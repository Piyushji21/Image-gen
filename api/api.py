
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import requests
import time
import base64
import os
import json
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="Kie AI Image Generator API")

API_KEY = "084521aaffe2f93d0dde3b72c7c4e08e"
BASE_URL = "https://api.kie.ai/api/v1"
UPLOAD_URL = "https://kieai.redpandaai.co/api/file-base64-upload"

class GenerateRequest(BaseModel):
    prompt: str
    model: str = "grok-imagine/text-to-image"
    aspect_ratio: str = "1:1"
    face_image_base64: Optional[str] = None  # Optional: send base64 directly

@app.get("/")
def home():
    return {"message": "Kie AI Image Generator API is running! Use /generate endpoint."}

@app.post("/generate")
async def generate_image(request: GenerateRequest):
    client = KieAIClient(API_KEY)
    
    face_url = None
    if request.face_image_base64:
        # If face is sent as base64, we can upload it (optional enhancement)
        face_url = client.upload_base64(request.face_image_base64)
    
    task_id = client.create_task(
        prompt=request.prompt,
        model=request.model,
        face_url=face_url,
        aspect_ratio=request.aspect_ratio
    )
    
    if not task_id:
        raise HTTPException(status_code=500, detail="Failed to create task")
    
    image_urls = client.poll_task(task_id)
    
    if not image_urls:
        raise HTTPException(status_code=500, detail="Generation failed or timed out")
    
    return JSONResponse({
        "success": True,
        "task_id": task_id,
        "image_urls": image_urls,
        "prompt": request.prompt
    })

# ==================== KieAIClient Class (from your previous code) ====================
class KieAIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = BASE_URL
        self.upload_url = UPLOAD_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def upload_base64(self, base64_str: str) -> Optional[str]:
        """Upload base64 image (if provided in request)"""
        try:
            payload = {"base64Data": base64_str if base64_str.startswith("data:") else f"data:image/png;base64,{base64_str}"}
            response = requests.post(self.upload_url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("data") or data.get("url")
        except Exception as e:
            print(f"Upload failed: {e}")
            return None

    def create_task(self, prompt: str, model: str = "grok-imagine/text-to-image",
                    face_url: Optional[str] = None, aspect_ratio: str = "1:1") -> Optional[str]:
        input_data = {"prompt": prompt, "aspect_ratio": aspect_ratio}
        if face_url:
            input_data["face_image"] = face_url
            input_data["main_face_image"] = face_url

        payload = {
            "model": model,
            "input": input_data,
            "callBackUrl": "https://mzpcoieakbomhtvxgftl.supabase.co/functions/v1/kie-callback?secret=kie_cb_2026"
        }

        try:
            response = requests.post(f"{self.base_url}/jobs/createTask", json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            res = response.json()
            if res.get("code") == 200:
                return res.get("data", {}).get("taskId") or res.get("data", {}).get("task_id")
        except Exception as e:
            print(f"Create task error: {e}")
        return None

    def poll_task(self, task_id: str, timeout: int = 180, interval: int = 6) -> List[str]:
        start = time.time()
        while time.time() - start < timeout:
            try:
                response = requests.get(
                    f"{self.base_url}/jobs/recordInfo",
                    params={"taskId": task_id},
                    headers=self.headers,
                    timeout=30
                )
                response.raise_for_status()
                res = response.json()
                if res.get("code") == 200:
                    data = res.get("data", {})
                    state = data.get("state") or data.get("status", "").lower()

                    if state == "success":
                        result_str = data.get("resultJson") or "{}"
                        try:
                            result_data = json.loads(result_str) if isinstance(result_str, str) else result_str
                        except:
                            result_data = {}
                        
                        urls = (result_data.get("resultUrls") or 
                                result_data.get("result_urls") or 
                                result_data.get("images") or [])
                        if urls:
                            return urls if isinstance(urls, list) else [urls]
                    elif state in ["fail", "error", "failed"]:
                        return []
            except:
                pass
            time.sleep(interval)
        return []

# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
