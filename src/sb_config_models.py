from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# TODO probably remove all that is not needed, as rules was messing it up...


class CorrelationFilter(BaseModel):
    ContentType: Optional[str] = None
    CorrelationId: Optional[str] = None
    Label: Optional[str] = None
    MessageId: Optional[str] = None
    ReplyTo: Optional[str] = None
    ReplyToSessionId: Optional[str] = None
    SessionId: Optional[str] = None
    To: Optional[str] = None
    Properties: Optional[Dict[str, Any]] = None


class RuleProperties(BaseModel):
    FilterType: str
    CorrelationFilter: CorrelationFilter


class Rule(BaseModel):
    Name: str
    Properties: RuleProperties


class SubscriptionProperties(BaseModel):
    DeadLetteringOnMessageExpiration: bool = False
    DefaultMessageTimeToLive: str = "PT1H"
    LockDuration: str = "PT1M"
    MaxDeliveryCount: int = 3
    ForwardDeadLetteredMessagesTo: str = ""
    ForwardTo: str = ""
    RequiresSession: bool = False


class Subscription(BaseModel):
    Name: str
    Properties: SubscriptionProperties
    # Rules: List[Rule] = []


class TopicProperties(BaseModel):
    DefaultMessageTimeToLive: str = "PT1H"
    DuplicateDetectionHistoryTimeWindow: str = "PT20S"
    RequiresDuplicateDetection: bool = False


class Topic(BaseModel):
    Name: str
    Properties: TopicProperties
    Subscriptions: List[Subscription] = []


class QueueProperties(BaseModel):
    DeadLetteringOnMessageExpiration: bool = False
    DefaultMessageTimeToLive: str = "PT1H"
    DuplicateDetectionHistoryTimeWindow: str = "PT20S"
    ForwardDeadLetteredMessagesTo: str = ""
    ForwardTo: str = ""
    LockDuration: str = "PT1M"
    MaxDeliveryCount: int = 3
    RequiresDuplicateDetection: bool = False
    RequiresSession: bool = False


class Queue(BaseModel):
    Name: str
    Properties: Optional[QueueProperties] = None


class Namespace(BaseModel):
    Name: str
    Queues: List[Queue] = []
    Topics: List[Topic] = []


class Logging(BaseModel):
    Type: str


class UserConfig(BaseModel):
    Namespaces: List[Namespace]
    Logging: Logging


class Configuration(BaseModel):
    UserConfig: UserConfig
