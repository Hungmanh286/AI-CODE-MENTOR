import requests
from fastapi import APIRouter

from app.core.config import settings

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
            input_messages = input_data.get("messages", [])

            question = None
            if input_messages and len(input_messages) > 0:
                first_message = input_messages[0]
                if isinstance(first_message, dict):
                    question = first_message.get("content")
                elif isinstance(first_message, str):
                    question = first_message

            output_data = trace_example.get("output", {})
            messages = output_data.get("messages", [])

            answer = None
            if messages and len(messages) > 0:
                last_message = messages[-1]
                if isinstance(last_message, dict):
                    answer = last_message.get("content")
                elif isinstance(last_message, str):
                    answer = last_message

            if answer:
                try:
                    import json

                    answer_json = json.loads(answer)
                    if isinstance(answer_json, dict) and "message" in answer_json:
                        answer = answer_json["message"]
                except (json.JSONDecodeError, ValueError):
                    pass

            history.append({"index": i + 1, "question": question, "answer": answer})
        return {"history": history}
    except requests.HTTPError as e:
        return {"error": str(e), "url": e.response.url, "response": e.response.text}
    except Exception as e:
        return {"error": str(e)}
