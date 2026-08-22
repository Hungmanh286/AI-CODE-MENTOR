from copilotkit import CopilotKitRemoteEndpoint, LangGraphAGUIAgent
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from dotenv import load_dotenv
from fastapi import FastAPI

from app.agents.question_expert import question_expert

load_dotenv()


app = FastAPI()
sdk = CopilotKitRemoteEndpoint(
    agents=[
        LangGraphAGUIAgent(
            name="generate_question",
            description="Manages question",
            graph=question_expert,
        )
    ],
)

add_fastapi_endpoint(app, sdk, "/copilotkit")
