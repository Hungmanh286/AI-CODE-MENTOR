import asyncio
import json
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    APIRouter,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    Query,
    status,
)
from langchain_community.callbacks import get_openai_callback

from langfuse.callback import CallbackHandler

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from redis.asyncio import Redis as AsyncRedis, ConnectionPool
from starlette.websockets import WebSocketState


from app.graph.workflow import build_workflow, invoke_workflow  # noqa


from app.schema import ChatResponse, ChatType, Role, ErrorCode, UserToken


from app.services import UserUsage, verify_access_token, safe_send
from app.config import settings


load_dotenv()


usage_redis_pool: ConnectionPool = None


async def get_tracer():
    try:
        tracer = CallbackHandler(
            tags=["code"],
            version=settings.VERSION,
        )
        yield tracer
    finally:
        tracer.langfuse.shutdown()


async def get_user_usage():
    redis_conn = AsyncRedis.from_pool(usage_redis_pool)
    try:
        yield UserUsage(redis_conn)
    finally:
        await redis_conn.close()


async def get_graph():
    """Get graph instance with PostgreSQL checkpointer.

    Returns:
        CompiledStateGraph: A compiled workflow graph with PostgreSQL checkpointer

    This function:
    1. Creates a connection to PostgreSQL database
    2. Initializes AsyncPostgresSaver to store conversation states
    3. Attaches the checkpointer to the global graph instance
    """
    try:
        async with AsyncPostgresSaver.from_conn_string(
            settings._checkpointer_db_uri
        ) as checkpointer:
            workflow = build_workflow()
            graph = workflow.compile(checkpointer=checkpointer)
            yield graph
    except Exception as e:
        print(f"Error initializing graph with checkpointer: {e}")
        raise


# async def get_pedagogical_graph():
#     """Get pedagogical agent graph"""
#     async for graph in get_graph(type="pedagogical"):
#         return graph


# async def get_feedback_graph():
#     """Get feedback agent graph"""
#     async for graph in get_graph(type="feedback"):
#         return graph


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application lifespan manager that initializes and cleans up resources."""
    global usage_redis_pool

    # rate limiting
    redis_config = {
        "max_connections": settings.REDIS_MAX_CONNECTION_POOL,
        "retry_on_timeout": True,
        "health_check_interval": 5,
    }

    usage_redis_pool = ConnectionPool.from_url(
        url=settings.RATELIMIT_REDIS, **redis_config
    )
    print("Initialized Redis connection pool")

    try:
        async with AsyncPostgresSaver.from_conn_string(
            settings._checkpointer_db_uri
        ) as checkpointer:
            try:
                await checkpointer.setup()
                print("Checkpointer setup completed")
            except Exception:
                print("Checkpointer already exists, skipping setup")
        yield

    finally:
        await asyncio.gather(
            usage_redis_pool.disconnect(),
        )
        print("Closed all connections!")


router = APIRouter(lifespan=lifespan)


async def handle_message(
    websocket: WebSocket,
    graph: CompiledStateGraph,
    message: str,
    session_uuid: str,
    question_id: str,
    user_token: UserToken,
    usage_client: UserUsage,
    tracer: CallbackHandler,
) -> None:
    """Handle message in background task

    Args:
        websocket (WebSocket): websocket connection
        graph (CompiledStateGraph): llm graph
        message (str): question string
        session_uuid (str): client session uuid
        question_id (str): question id
        user_token (UserToken): user token object from jwt token
        usage_client (UserUsage): user usage client
        tracer (CallbackHandler): LLM tracer object
    """
    try:
        is_limited = await usage_client.isratelimit(
            user_id=user_token.user_id, rate_limit=user_token.token_limit
        )
        if is_limited:
            print(f"User {user_token.user_id} usage limit exceeded.")
            resp = ChatResponse(
                role=Role.bot,
                content=f"Usage limit exceeded. Try again after {settings.RATELIMIT_WINDOW_MINUTES} minutes",
                type=ChatType.error,
                session=session_uuid,
                question_id=question_id,
                error_code=ErrorCode.ratelimit_error,
            )
            await safe_send(websocket, resp)
            return

        with get_openai_callback() as cb:
            await invoke_workflow(
                websocket=websocket,
                graph=graph,
                message=message,
                session_uuid=session_uuid,
                question_id=question_id,
                user_token=user_token,
                tracer=tracer,
            )

            tokens_usage = cb.total_tokens

        await usage_client.update_usage(user_token.user_id, tokens_usage)
    except Exception as e:
        print(f"Error processing message: {e}")
        resp = ChatResponse(
            role=Role.bot,
            content="Sorry, something went wrong.",
            type=ChatType.error,
            session=session_uuid,
            question_id=question_id,
            error_code=ErrorCode.server_error,
        )
        await safe_send(websocket, resp)


@router.websocket("/chat/pedagogical")
async def websocket_endpoint_pedagogical_agent(
    websocket: WebSocket,
    token: str = Query("", title="Token", description="authen token"),
    usage_client: UserUsage = Depends(get_user_usage),
    graph: CompiledStateGraph = Depends(get_graph),
    tracer: CallbackHandler = Depends(get_tracer),
    session_uuid: str = Query(None, title="Session UUID", description="Session UUID"),
):
    try:
        user_dict = verify_access_token(token)
        user_token = UserToken.model_validate(user_dict)
    except Exception as e:
        print(f"Token is incorrect: {e}")
        # user_token = UserToken(user_id="000000", username="Tester01", token_limit=1000000)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    # random_session_uuid = str(uuid.uuid4())
    # session_uuid = None
    question_id = ""

    is_limited = await usage_client.isratelimit(
        user_id=user_token.user_id, rate_limit=user_token.token_limit
    )
    if is_limited:
        print(f"User {user_token.user_id} usage limit exceeded.")
        resp = ChatResponse(
            role=Role.bot,
            content=f"Usage limit exceeded. Try again after {settings.RATELIMIT_WINDOW_MINUTES} minutes",
            type=ChatType.error,
            session=session_uuid,
            question_id=question_id,
            error_code=ErrorCode.ratelimit_error,
        )
        await safe_send(websocket, resp)

    resp = ChatResponse(
        role=Role.bot,
        content=json.dumps(
            {
                "username": user_token.username,
                "token_limit": user_token.token_limit,
            },
            ensure_ascii=False,
        ),
        type=ChatType.info,
        session=session_uuid,
        question_id=question_id,
    )
    await safe_send(websocket, resp)

    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            data = await websocket.receive_text()
            payload = json.loads(data)
            if not isinstance(payload, dict):
                raise ValueError("Invalid JSON format")

            if not (message := payload.get("content", "").strip()):
                continue

            question_id = payload.get("question_id", "").strip()
            session_uuid = payload.get("uuid", session_uuid)
            asyncio.create_task(
                handle_message(
                    websocket=websocket,
                    graph=graph,
                    message=message,
                    session_uuid=session_uuid,
                    question_id=question_id,
                    usage_client=usage_client,
                    user_token=user_token,
                    tracer=tracer,
                )
            )
    except WebSocketDisconnect:
        print(f"Connection disconnected {session_uuid}.")
    except RuntimeError as e:
        print(f"RuntimeError occurred: {e}")
    except Exception as e:
        print(f"Error in {session_uuid}: {e}")
        resp = ChatResponse(
            role=Role.bot,
            content="Sorry, something went wrong.",
            type=ChatType.error,
            session=session_uuid,
            question_id=question_id,
            error_code=ErrorCode.server_error,
        )
        await safe_send(websocket, resp)
