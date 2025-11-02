import requests
from fastapi import APIRouter

from app.config import settings

LANGFUSE_HOST = settings.LANGFUSE_HOST
LANGFUSE_PUBLIC_KEY = settings.LANGFUSE_PUBLIC_KEY
LANGFUSE_SECRET_KEY = settings.LANGFUSE_SECRET_KEY

router = APIRouter()


@router.get("/history-chat/{session_id}")
def get_history_chat(session_id: str):
    try:
        trace_url = f"{LANGFUSE_HOST}/api/public/sessions/{session_id}"
        session_res = requests.get(
            trace_url, auth=(LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY)
        )
        session_res.raise_for_status()
        session = session_res.json()
        traces = session.get("traces", [])
        history = []
        for i, trace_example in enumerate(traces):
            input_data = trace_example.get("input", {})
            question = input_data.get("messages", [{}])[0].get("content")
            output_data = trace_example.get("output", {})
            messages = output_data.get("messages", [])
            answer = messages[-1].get("content") if messages else None
            history.append({"index": i + 1, "question": question, "answer": answer})
        return {"history": history}
    except requests.HTTPError as e:
        return {"error": str(e), "url": e.response.url, "response": e.response.text}
    except Exception as e:
        return {"error": str(e)}
