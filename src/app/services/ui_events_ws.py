import asyncio
import json
import logging
import socket
import threading
from typing import Any, Dict, List, Optional

import websockets

logger = logging.getLogger(__name__)

_loop: Optional[asyncio.AbstractEventLoop] = None
_thread: Optional[threading.Thread] = None
_clients: "set[websockets.WebSocketServerProtocol]" = set()
_queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
_running = False
_server: Optional[websockets.WebSocketServer] = None


async def _producer() -> None:
  """
  从队列中读取事件并广播给所有已连接客户端。
  """
  while _running:
    event = await _queue.get()
    if event is None:  # type: ignore[comparison-overlap]
      continue
    data = json.dumps(event)
    dead: List[websockets.WebSocketServerProtocol] = []
    for ws in list(_clients):
      try:
        await ws.send(data)
      except Exception as e:
        logger.warning("Failed to send UI event to client: %s", e)
        dead.append(ws)
    for ws in dead:
      try:
        _clients.discard(ws)
      except Exception:
        pass


async def _handler(websocket: websockets.WebSocketServerProtocol) -> None:
  """
  UI WebSocket 处理函数。

  当前仅用于下发事件，不处理来自前端的消息。
  
  注意：websockets 15.0+ 中，handler 函数只接受一个参数（websocket）。
  """
  _clients.add(websocket)
  logger.info("UI WebSocket client connected: %s", websocket.remote_address)
  try:
    async for _ in websocket:
      # 忽略前端发送的任何内容
      continue
  except Exception as e:
    logger.info("UI WebSocket client disconnected: %s", e)
  finally:
    _clients.discard(websocket)


def enqueue_ui_event(event: Dict[str, Any]) -> None:
  """
  将事件放入队列，由后台任务异步广播给所有客户端。
  """
  if not _running or _loop is None:
    return
  try:
    asyncio.run_coroutine_threadsafe(_queue.put(event), _loop)
  except Exception as e:
    logger.debug("enqueue_ui_event failed: %s", e)


def _is_port_in_use(host: str, port: int) -> bool:
  """
  检查端口是否已被占用。
  """
  with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    try:
      s.bind((host, port))
      return False
    except OSError:
      return True


def start_ui_ws_server(host: str = "0.0.0.0", port: int = 8766) -> None:
  """
  启动面向前端的 WebSocket 服务，用于下发统一 UI 事件流。

  注意：当前实现为独立端口，推荐在生产环境通过反向代理将 /ws/ui-events
  路由到该服务。
  
  如果端口已被占用，会记录警告并跳过启动。
  
  注意：在 Flask reloader 模式下，只在子进程中启动服务器（通过检查
  WERKZEUG_RUN_MAIN 环境变量）。
  """
  import os
  
  # Flask reloader 检查：
  # - 如果 WERKZEUG_RUN_MAIN 为 None，说明不在 reloader 模式下，直接启动
  # - 如果 WERKZEUG_RUN_MAIN 为 'true'，说明是 reloader 子进程（实际运行应用的进程），应该启动
  # - 如果 WERKZEUG_RUN_MAIN 为 'false' 或其他值，说明是 reloader 父进程，不应该启动
  werkzeug_run_main = os.environ.get("WERKZEUG_RUN_MAIN")
  if werkzeug_run_main == "false":
    # 在 reloader 父进程中，不启动服务器
    logger.debug("Skipping UI WebSocket server start in reloader parent process")
    return
  
  global _loop, _thread, _running, _server
  if _running:
    logger.warning("UI WebSocket server is already running, skipping start.")
    return
  
  # 移除端口预检查，直接尝试绑定
  # 如果端口被占用，会在 _async_main 的异常处理中捕获并记录
  _running = True

  def _run() -> None:
    global _loop, _server, _queue
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    # 在新 Loop 中重新初始化队列，确保其绑定到正确的 Loop
    _queue = asyncio.Queue()

    async def _async_main() -> None:
      """
      在事件循环中启动 WebSocket 服务。

      注意：必须在已有 running loop 中调用 websockets.serve，
      否则 websockets 会在内部调用 get_running_loop() 抛出错误。
      """
      global _server, _running
      try:
        _server = await websockets.serve(
          _handler,
          host,
          port,
          ping_interval=20,
          ping_timeout=20,
        )
        logger.info("UI WebSocket server started at ws://%s:%d/ui-events", host, port)
        # 启动事件生产者任务
        _loop.create_task(_producer())
        # 等待服务器关闭（通常不会发生，除非进程退出）
        await _server.wait_closed()
      except OSError as e:
        # 端口被占用是正常的（可能是 reloader 父进程已绑定），只记录 debug 级别日志
        if "Address already in use" in str(e) or "address already in use" in str(e).lower():
          logger.debug(
            "Port %d is already in use (likely by reloader parent process). "
            "UI WebSocket server will not start in this process.",
            port
          )
        else:
          logger.error(
            "Failed to start UI WebSocket server on %s:%d: %s. "
            "The port may be in use or there may be a permission issue.",
            host, port, e
          )
        _running = False

    try:
      _loop.run_until_complete(_async_main())
    except Exception as e:
      logger.error("UI WebSocket server thread error: %s", e, exc_info=True)
      global _running
      _running = False
    finally:
      if _loop.is_running():
        _loop.stop()
      _loop.close()

  _thread = threading.Thread(target=_run, daemon=True)
  _thread.start()


