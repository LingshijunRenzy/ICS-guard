"""
服务层包。

提供以下服务模块：
- controller_client: 调用 SDN 控制层 REST API
- event_subscriber: 订阅控制层 WebSocket 事件
- inference: 本地 AI 模型加载与推理
"""

from .controller_client import (
    ControllerClient,
    ControllerClientError,
    AuthenticationError,
    TokenExpiredError,
    TokenPair,
    NodeStatus,
    LinkStatus,
    get_controller_client,
    reset_controller_client,
)

from .event_subscriber import (
    EventType,
    Event,
    EventHandler,
    EventSubscriberManager,
    get_event_subscriber,
    reset_event_subscriber,
)

from .inference import (
    DecisionLevel,
    PredictionResult,
    ThresholdConfig,
    FeatureConfig,
    InferenceService,
    get_inference_service,
    init_inference_service,
    reset_inference_service,
)

__all__ = [
    # controller_client
    "ControllerClient",
    "ControllerClientError",
    "AuthenticationError",
    "TokenExpiredError",
    "TokenPair",
    "NodeStatus",
    "LinkStatus",
    "get_controller_client",
    "reset_controller_client",
    # event_subscriber
    "EventType",
    "Event",
    "EventHandler",
    "EventSubscriberManager",
    "get_event_subscriber",
    "reset_event_subscriber",
    # inference
    "DecisionLevel",
    "PredictionResult",
    "ThresholdConfig",
    "FeatureConfig",
    "InferenceService",
    "get_inference_service",
    "init_inference_service",
    "reset_inference_service",
]
