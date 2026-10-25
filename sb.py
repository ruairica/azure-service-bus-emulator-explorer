import asyncio
import json
from typing import Any, Callable, Dict, List

from azure.servicebus import (
    ServiceBusClient,
    ServiceBusMessage,
    ServiceBusReceivedMessage,
)
from fasthtml.common import *
from monsterui.all import *

from models import (
    Config,
    Configuration,
    MessageProperty,
    Namespace,
    Rule,
    SbMessage,
    SbMessageSave,
    SentMessage,
)

hdrs = (
    Script(src="https://unpkg.com/htmx-ext-sse@2.2.1/sse.js"),
    (Theme.violet.headers()),
    SortableJS(".sortable"),
    Link(
        rel="icon",
        href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🔥</text></svg>",
    ),
)


app, rt = fast_app(live=False, hdrs=hdrs)


db = database("sb.db")
configs = db.create(Config)
sent_messages = db.create(SentMessage)
message_properties = db.create(MessageProperty)


@rt("/")
def get(request=None):
    return _create_page(
        home_page(),
        request,
    )


def home_page():
    return Container(
        H1("SB Emulator Explorer"),
        Form(
            DivCentered(
                Grid(
                    LabelInput(
                        "Full Path To configuration file",
                        id="configFilePath",
                        placeholder=r"C:\Source\Testing\sbconfig.json",
                    ),
                    LabelInput("Save as", id="name", placeholder="email notifier sb"),
                    Div(
                        Button(
                            "Load File",
                            cls=(ButtonT.primary, "mt-auto"),
                            type="submit",
                        ),
                        cls="flex",
                    ),
                ),
                cls="mt-24",
            ),
            hx_post="/loadconfig",
            hx_swap="outerHTML",
            hx_target=".thesidebar",
        ),
        Div(
            H3("Previously saved"),
            P("Drag to reorder", cls=(TextPresets.muted_sm, "mb-2")),
            Form(
                *[
                    Card(
                        Hidden(id="id", value=x.id),
                        header=Div(
                            CardTitle(x.name), P(x.path, cls=TextPresets.muted_sm)
                        ),
                        footer=Div(
                            Button(
                                "Delete",
                                hx_target=f"#saved-card{x.id}",
                                hx_swap="delete",
                                hx_delete=f"/configs/{x.id}",
                                cls=ButtonT.destructive,
                            ),
                            Button(
                                "Use",
                                type="button",
                                hx_get=f"/configs/{x.id}",
                                hx_swap="outerHTML",
                                hx_target=".thesidebar",
                                hx_push_url="true",
                                cls=ButtonT.primary,
                            ),
                            cls="space-x-2",
                        ),
                        id=f"saved-card{x.id}",
                    )
                    for x in configs(order_by="priority")
                ],
                id="configs-list",
                cls="sortable space-y-4",
                hx_post="/configs/reorder",
                hx_trigger="end",
            ),
            cls="mt-8",
            id="saved-configs-container",
        ),
    )


@dataclass
class ConfigForm:
    configFilePath: str
    name: str


@rt("/configs/{configId}")
def delete(configId: int):
    configs.delete(configId)
    return Div()


@rt("/configs/reorder")
def post(id: list[int]):
    for i, id_ in enumerate(id):
        configs.update({"priority": i}, id_)
    return tuple(
        Card(
            Hidden(id="id", value=x.id),
            header=Div(CardTitle(x.name), P(x.path, cls=TextPresets.muted_sm)),
            footer=Div(
                Button(
                    "Delete",
                    hx_target=f"#saved-card{x.id}",
                    hx_swap="delete",
                    hx_delete=f"/configs/{x.id}",
                    cls=ButtonT.destructive,
                ),
                Button(
                    "Use",
                    type="button",
                    hx_get=f"/configs/{x.id}",
                    hx_swap="outerHTML",
                    hx_target=".thesidebar",
                    hx_push_url="true",
                    cls=ButtonT.primary,
                ),
                cls="space-x-2",
            ),
            id=f"saved-card{x.id}",
        )
        for x in configs(order_by="priority")
    )


connection = ServiceBusClient.from_connection_string(
    conn_str="Endpoint=mytester://localhost;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=SAS_KEY_VALUE;UseDevelopmentEmulator=true;"
)


@rt("/configs/{configId}")
def get(configId: int, request=None):
    try:
        if not is_htmx(request):
            return _create_page(home_page(), request, configId)
        else:
            return sidebar(configId), Toast(
                DivLAligned(UkIcon("check-circle", cls="mr-2"), "Loaded configuration"),
                id="success-toast",
                dur=0.5,
                alert_cls=AlertT.success,
                cls=(ToastHT.start, ToastVT.top),
            )
    except Exception as e:
        return Toast(
            DivLAligned(UkIcon("square-x", cls="mr-2"), f"Failed to load config: {e}"),
            id="error-toast",
            dur=7,
            alert_cls=AlertT.error,
            cls=(ToastHT.end, ToastVT.bottom),
        )


@rt("/loadconfig")  # this might be hard to refirect url ?
def post(form: ConfigForm):
    excaped_path = form.configFilePath.strip('"')
    try:
        config = Configuration.model_validate_json(open(excaped_path).read())
        if form.name != "":
            c = configs.insert(Config(path=excaped_path, name=form.name, priority=0))
            print(c)
            return Redirect(f"/configs/{c.id}")
    except Exception as e:
        return Toast(
            DivLAligned(UkIcon("square-x", cls="mr-2"), f"Failed to load config: {e}"),
            id="error-toast",
            dur=7,
            alert_cls=AlertT.error,
            cls=(ToastHT.end, ToastVT.bottom),
        )


messagePropertyTypes: Dict[str, Callable[[str], Any]] = {
    "String": lambda x: x,
    "Boolean": lambda x: x.lower() == "true",
    "Int32": lambda x: int(x),
    "Char": lambda x: x,
}


@rt("/{namespace}/{entity}/send")
async def post(entity: str, message: SbMessage):
    try:
        headers = {
            x[0]: messagePropertyTypes[x[1]](x[2])
            for x in zip(
                message.messagePropertyKeys,
                message.messagePropertyContentTypes,
                message.messagePropertyValues,
            )
            if x[0] != ""
        }

        sender = connection.get_topic_sender(topic_name=entity)
        sbMessage = ServiceBusMessage(
            body=message.body,
            content_type=message.messageContentType,
            application_properties=headers,
        )
        with sender:
            sender.send_messages(sbMessage)

        return Toast(
            DivLAligned(
                UkIcon("check-circle", cls="mr-2"), "Message sent successfully"
            ),
            id="success-toast",
            dur=2,
            alert_cls=AlertT.success,
            cls=(ToastHT.end, ToastVT.bottom),
        )

    except Exception as e:
        print(e)
        return Toast(
            DivLAligned(UkIcon("square-x", cls="mr-2"), f"Failed to send: {e}"),
            id="error-toast",
            dur=7,
            alert_cls=AlertT.error,
            cls=(ToastHT.end, ToastVT.bottom),
        )


@rt("/{namespace}/{queue}/queue/send")
async def post(queue: str, message: SbMessage):
    try:
        headers = {
            x[0]: messagePropertyTypes[x[1]](x[2])
            for x in zip(
                message.messagePropertyKeys,
                message.messagePropertyContentTypes,
                message.messagePropertyValues,
            )
            if x[0] != ""
        }

        sender = connection.get_queue_sender(queue_name=queue)
        sbMessage = ServiceBusMessage(
            body=message.body,
            content_type=message.messageContentType,
            application_properties=headers,
        )
        with sender:
            sender.send_messages(sbMessage)

        return Toast(
            DivLAligned(
                UkIcon("check-circle", cls="mr-2"), "Message sent successfully to queue"
            ),
            id="success-toast",
            dur=2,
            alert_cls=AlertT.success,
            cls=(ToastHT.end, ToastVT.bottom),
        )

    except Exception as e:
        print(e)
        return Toast(
            DivLAligned(
                UkIcon("square-x", cls="mr-2"), f"Failed to send to queue: {e}"
            ),
            id="error-toast",
            dur=7,
            alert_cls=AlertT.error,
            cls=(ToastHT.end, ToastVT.bottom),
        )


@rt("/{namespace}/{entity}/send/save")
async def post(namespace: str, entity: str, form: SbMessageSave):
    msg = sent_messages.insert(
        SentMessage(
            name=form.formName,
            body=form.body,
            namespace=namespace,
            entity=entity,
            messageContentType=form.messageContentType,
            priority=0,
        )
    )
    for key, content_type, value in zip(
        form.messagePropertyKeys,
        form.messagePropertyContentTypes,
        form.messagePropertyValues,
    ):
        message_properties.insert(
            MessageProperty(
                sent_message_id=msg.id,
                key=key,
                content_type=content_type,
                value=value,
            )
        )

    return prev_saved_cards(namespace, entity)


@rt("/elements/mp")
def get(req):
    new_id = len(req.query_params.getlist("messagePropertyKeys"))
    return message_header_row(new_id)


@rt("/configs/{configId}/namespaces/{namespace}/topics/{topic}/send")
def get(configId: int, namespace: str, topic: str, request=None):
    return _create_page(
        Container(
            Modal(
                ModalTitle("Select a name for your saved message"),
                Form(
                    LabelInput("Name", id="formName"),
                    Button(
                        "Save",
                        type="submit",
                        cls=ButtonT.primary,
                    ),
                    hx_post=f"/{namespace}/{topic}/send/save",
                    hx_include="#send-message-form",
                    hx_target="#saved-sent-messages-container",
                    hx_swap="outerHTML",
                    hx_on__after_request="UIkit.modal('#save-message-modal').hide()",
                ),
                footer=Div(ModalCloseButton("Close", cls=ButtonT.secondary)),
                id="save-message-modal",
            ),
            Div(cls="space-y-4")(
                DivCentered(
                    H3("Send Message"),
                    P(f"To {namespace} - {topic}", cls=TextPresets.muted_sm),
                ),
                send_message_form(namespace, topic),
                prev_saved_cards(namespace, topic),
            ),
        ),
        request,
        config_id=configId,
    )


def prev_saved_cards(namespace: str, entity: str):
    return Div(
        H3("Previously saved"),
        P("Drag to reorder", cls=(TextPresets.muted_sm, "mb-2")),
        Form(
            *[
                Card(
                    Hidden(id="id", value=x.id),
                    header=CardTitle(x.name),
                    footer=Div(
                        Button(
                            "Delete",
                            hx_target=f"#saved-card{x.id}",
                            hx_swap="delete",
                            hx_delete=f"/savedmessages/delete/{x.id}",
                            cls=ButtonT.destructive,
                        ),
                        Button(
                            "Use",
                            type="button",
                            hx_get=f"/{namespace}/{entity}/savedmessages/use/{x.id}",
                            hx_swap="outerHTML",
                            hx_target="#send-message-form",
                            cls=ButtonT.primary,
                        ),
                        cls="space-x-2",
                    ),
                    id=f"saved-card{x.id}",
                )
                for x in sent_messages(
                    where=f"namespace='{namespace}' AND entity='{entity}'",
                    order_by="priority",
                )
            ],
            id="saved-messages-list",
            cls="sortable space-y-4",
            hx_post=f"/{namespace}/{entity}/savedmessages/reorder",
            hx_trigger="end",
        ),
        id="saved-sent-messages-container",
    )


@rt("/savedmessages/delete/{savedMessageId}")
def delete(savedMessageId: int):
    for prop in message_properties(where=f"sent_message_id = {savedMessageId}"):
        message_properties.delete(prop.id)
    sent_messages.delete(savedMessageId)
    return Div()


@rt("/{namespace}/{entity}/savedmessages/reorder")
def post(namespace: str, entity: str, id: list[int]):
    for i, id_ in enumerate(id):
        sent_messages.update({"priority": i}, id_)
    return tuple(
        Card(
            Hidden(id="id", value=x.id),
            header=CardTitle(x.name),
            footer=Div(
                Button(
                    "Delete",
                    hx_target=f"#saved-card{x.id}",
                    hx_swap="delete",
                    hx_delete=f"/savedmessages/delete/{x.id}",
                    cls=ButtonT.destructive,
                ),
                Button(
                    "Use",
                    type="button",
                    hx_get=f"/{namespace}/{entity}/savedmessages/use/{x.id}",
                    hx_swap="outerHTML",
                    hx_target="#send-message-form",
                    cls=ButtonT.primary,
                ),
                cls="space-x-2",
            ),
            id=f"saved-card{x.id}",
        )
        for x in sent_messages(
            where=f"namespace='{namespace}' AND entity='{entity}'",
            order_by="priority",
        )
    )


def send_message_form(
    namespace: str,
    entity: str,
    messageBodyValue="",
    contentTypevalue="application/json",
    headers: List[List[str]] = [],
    post_url: str = None,
):
    headerRows = (
        [
            message_header_row(i, key=x[0], ct=x[1], val=x[2])
            for i, x in enumerate(headers)
        ]
        if headers
        else [message_header_row(0)]
    )
    if post_url is None:
        post_url = f"/{namespace}/{entity}/send"
    return Form(
        id="send-message-form",
        cls="space-y-4",
        hx_post=post_url,
        hx_target="#send-message-form",
        hx_swap="afterend",
    )(
        Grid(
            Div(
                H4("Message Body"),
                LabelTextArea(
                    "Text",
                    id="body",
                    value=messageBodyValue,
                    name="body",
                    input_cls="h-32",
                ),
                LabelSelect(
                    Option(
                        "Select Content Type",
                        value="",
                        selected=True,
                        disabled=True,
                    ),
                    Option("application/json"),
                    Option("application/xml"),
                    label="Content Type",
                    value=contentTypevalue,
                    name="messageContentType",
                    id="messageContentType",
                    cls="w-64",
                ),
                cls="space-y-4",
            ),
            Div(
                H4("Message Headers"),
                Fieldset(
                    *headerRows,
                    id="messageproperties",
                    cls="space-y-4",
                ),
                Button(
                    "Add Header",
                    hx_get="/elements/mp",
                    hx_include="[name='messagePropertyKeys']",
                    target_id="messageproperties",
                    hx_swap="beforeend",
                    cls=ButtonT.primary,
                    type="button",
                ),
                cls="space-y-4",
            ),
        ),
        Div(
            Button(
                "Save For Later",
                type="button",
                data_uk_toggle="target: #save-message-modal",
                cls=ButtonT.secondary,
            ),
            Button("Send", cls=ButtonT.primary, type="submit"),
            cls=("justify-end", "flex", "space-x-4"),
        ),
    )


@rt("/{namespace}/{entity}/savedmessages/use/{savedMessageId}")
def get(namespace: str, entity: str, savedMessageId: int):
    item = sent_messages[savedMessageId]
    props = message_properties(where=f"sent_message_id = {savedMessageId}")
    headers = [[p.key, p.content_type, p.value] for p in props]

    return send_message_form(
        namespace,
        entity,
        item.body,
        item.messageContentType,
        headers,
    )


@rt("/elements/blank")
def get():
    return Div()


# There is more properties that can be added to the message display, need to decide what's important.
def queue_message_display(
    namespace: str, queue: str, message: ServiceBusReceivedMessage, message_type: str
):
    return Div(
        Div(
            P(f"{message.sequence_number}: {message.message_id}"),
            P(f"Enqueued at {message.enqueued_time_utc.strftime('%Y-%m-%d %H:%M:%S')}"),
            hx_trigger="click",
            hx_get=f"/{namespace}/{queue}/messages/{message_type}/{message.sequence_number}",
            hx_target="#enlarged-message",
            hx_swap="outerHTML",
            cls=("cursor-pointer", "hover:bg-secondary", "p-2"),
        ),
        Divider(),
    )


def active_message_display(
    namespace: str, entity: str, subscription: str, message: ServiceBusReceivedMessage
):
    return Div(
        Div(
            P(f"{message.sequence_number}: {message.message_id}"),
            P(f"Enqueued at {message.enqueued_time_utc.strftime('%Y-%m-%d %H:%M:%S')}"),
            hx_trigger="click",
            hx_get=f"/{namespace}/{entity}/{subscription}/messages/active/{message.sequence_number}",
            hx_target="#enlarged-message",
            hx_swap="outerHTML",
            cls=("cursor-pointer", "hover:bg-secondary", "p-2"),
        ),
        Divider(),
    )


def deadlettered_message_display(
    namespace: str, entity: str, subscription: str, message: ServiceBusReceivedMessage
):
    return Div(
        Div(
            P(f"{message.sequence_number}: {message.message_id}"),
            P(f"Enqueue at {message.enqueued_time_utc.strftime('%Y-%m-%d %H:%M:%S')}"),
            hx_trigger="click",
            hx_get=f"/{namespace}/{entity}/{subscription}/messages/deadlettered/{message.sequence_number}",
            hx_target="#enlarged-message",
            hx_swap="outerHTML",
            cls=("cursor-pointer", "hover:bg-secondary", "p-2"),
        ),
        Divider(),
    )


# get the enlarged message for an active message that has been clicked on
@rt("/{namespace}/{entity}/{subscription}/messages/active/{message_sequence_number}")
def get(namespace: str, entity: str, subscription: str, message_sequence_number: int):
    return larger_message_display(
        namespace, entity, subscription, message_sequence_number
    )


# get the enlarged message for a dead lettered message that has been clicked on
@rt(
    "/{namespace}/{entity}/{subscription}/messages/deadlettered/{message_sequence_number}"
)
def get(namespace: str, entity: str, subscription: str, message_sequence_number: int):
    return larger_message_display(
        namespace, entity, f"{subscription}/$deadletterqueue", message_sequence_number
    )


# delete an active message from a topic subscription
@rt(
    "/{namespace}/{entity}/{subscription}/messages/active/{message_sequence_number}/delete"
)
def delete(
    namespace: str, entity: str, subscription: str, message_sequence_number: int
):
    """Delete an active message from a topic subscription"""
    with connection.get_subscription_receiver(
        topic_name=entity, subscription_name=subscription, max_wait_time=5
    ) as receiver:
        success, error = delete_message_by_sequence(receiver, message_sequence_number)

        if success:
            return (
                Div(H4("View"), id="enlarged-message"),
                Toast(
                    DivLAligned(
                        UkIcon("check-circle", cls="mr-2"),
                        "Message deleted successfully",
                    ),
                    id="success-toast",
                    dur=2,
                    alert_cls=AlertT.success,
                    cls=(ToastHT.end, ToastVT.bottom),
                ),
            )
        else:
            return Toast(
                DivLAligned(
                    UkIcon("square-x", cls="mr-2"), f"Failed to delete: {error}"
                ),
                id="error-toast",
                dur=5,
                alert_cls=AlertT.error,
                cls=(ToastHT.end, ToastVT.bottom),
            )


# delete a dead-lettered message from a topic subscription
@rt(
    "/{namespace}/{entity}/{subscription}/messages/deadlettered/{message_sequence_number}/delete"
)
def delete(
    namespace: str, entity: str, subscription: str, message_sequence_number: int
):
    """Delete a dead-lettered message from a topic subscription"""
    with connection.get_subscription_receiver(
        topic_name=entity,
        subscription_name=f"{subscription}/$deadletterqueue",
        max_wait_time=5,
    ) as receiver:
        success, error = delete_message_by_sequence(receiver, message_sequence_number)

        if success:
            return (
                Div(H4("View"), id="enlarged-message"),
                Toast(
                    DivLAligned(
                        UkIcon("check-circle", cls="mr-2"),
                        "Dead-lettered message deleted successfully",
                    ),
                    id="success-toast",
                    dur=2,
                    alert_cls=AlertT.success,
                    cls=(ToastHT.end, ToastVT.bottom),
                ),
            )
        else:
            return Toast(
                DivLAligned(
                    UkIcon("square-x", cls="mr-2"), f"Failed to delete: {error}"
                ),
                id="error-toast",
                dur=5,
                alert_cls=AlertT.error,
                cls=(ToastHT.end, ToastVT.bottom),
            )


def larger_message_display(
    namespace: str, entity: str, subscription: str, message_sequence_number: int
):
    # Determine if this is a dead letter message
    is_dead_letter = subscription.endswith("/$deadletterqueue")
    original_subscription = (
        subscription.replace("/$deadletterqueue", "")
        if is_dead_letter
        else subscription
    )
    message_type = "deadlettered" if is_dead_letter else "active"

    with connection.get_subscription_receiver(
        topic_name=entity, subscription_name=subscription
    ) as receiver:
        peeked_message = receiver.peek_messages(
            max_message_count=1, sequence_number=message_sequence_number
        )[0]
        print(peeked_message)
        return (
            Div(
                H4("View", cls="mb-8"),
                H5("Message ID", cls="my-2"),
                P(peeked_message.message_id),
                H5("Content type", cls="my-2"),
                P(peeked_message.content_type),
                H5("Body", cls="my-2"),
                Pre(
                    format_message_body(peeked_message.body),
                    cls="overflow-auto max-h-96",
                ),
                H5("Headers", cls="my-2"),
                Table(
                    Tr(Th("key"), Th("Value")),
                    *[
                        Tr(Td(message_to_string(k)), Td(message_to_string(v)))
                        for k, v in (
                            peeked_message.application_properties.items()
                            if peeked_message.application_properties
                            else []
                        )
                    ],
                ),
                # Delete button and modal
                Div(
                    Button(
                        "Delete Message",
                        type="button",
                        data_uk_toggle=f"target: #delete-message-modal-{message_sequence_number}",
                        cls=(ButtonT.destructive, "mt-8"),
                    ),
                    Modal(
                        ModalTitle("Confirm Delete"),
                        P(
                            "Are you sure you want to delete this message? This action cannot be undone.",
                            cls="my-4",
                        ),
                        footer=Div(
                            ModalCloseButton("Cancel", cls=ButtonT.secondary),
                            Button(
                                "Delete",
                                hx_delete=f"/{namespace}/{entity}/{original_subscription}/messages/{message_type}/{message_sequence_number}/delete",
                                hx_target="#enlarged-message",
                                hx_swap="outerHTML",
                                hx_on__after_request=f"UIkit.modal('#delete-message-modal-{message_sequence_number}').hide()",
                                cls=ButtonT.destructive,
                            ),
                            cls="flex gap-2",
                        ),
                        id=f"delete-message-modal-{message_sequence_number}",
                    ),
                    cls="mt-8",
                ),
                id="enlarged-message",
            ),
        )


def message_to_string(x):
    if hasattr(x, "__iter__") and not isinstance(x, (str, bytes)):
        # Join the bytes parts and then decode
        return b"".join(x).decode("utf-8")
    elif isinstance(x, bytes):
        return x.decode("utf-8")
    else:
        return str(x)


def format_message_body(body) -> str:
    """Convert message body to string, pretty-printing JSON if detected."""
    text = message_to_string(body)
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, indent=2)
    except (json.JSONDecodeError, TypeError):
        return text


def delete_message_by_sequence(receiver, sequence_number: int, max_messages: int = 100):
    """Delete a specific message by sequence number.

    Args:
        receiver: Azure Service Bus receiver instance
        sequence_number: Sequence number of the message to delete
        max_messages: Maximum messages to receive while searching

    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    try:
        messages = receiver.receive_messages(
            max_message_count=max_messages, max_wait_time=5
        )

        target_message = None
        for msg in messages:
            if msg.sequence_number == sequence_number:
                target_message = msg
            else:
                # Return non-target messages back to queue
                receiver.abandon_message(msg)

        if target_message:
            receiver.complete_message(target_message)
            return (True, None)
        else:
            return (False, "Message not found or already processed")

    except Exception as e:
        return (False, str(e))


def subscription_rules(
    configId: int, namespace: str, topic: str, subscription: str
) -> list[Rule]:
    "Look up a subscription's rules in the saved configuration file"
    return next(
        (
            s.Rules
            for n in load_namespaces(configId)
            if n.Name == namespace
            for t in n.Topics
            if t.Name == topic
            for s in t.Subscriptions
            if s.Name == subscription
        ),
        [],
    )


def rule_display(rule: Rule):
    props = rule.Properties
    if props.SqlFilter is not None:
        filter_content = CodeBlock(props.SqlFilter.SqlExpression or "")
    elif props.CorrelationFilter is not None:
        fields = props.CorrelationFilter.model_dump(exclude_none=True)
        fields |= {
            f"Properties.{k}": v for k, v in fields.pop("Properties", {}).items()
        }
        filter_content = Table(
            Tr(Th("Field"), Th("Value")),
            *[Tr(Td(k), Td(str(v))) for k, v in fields.items()],
        )
    else:
        filter_content = P("No filter defined", cls=TextPresets.muted_sm)
    action = props.Action and props.Action.SqlExpression
    return Card(
        filter_content,
        (
            Div(P("Action", cls="font-semibold mt-4 mb-2"), CodeBlock(action))
            if action
            else ""
        ),
        header=DivLAligned(
            H5(rule.Name), Label(props.FilterType, cls=LabelT.secondary)
        ),
    )


def rules_display(rules: list[Rule]):
    return Div(
        H4(f"Rules ({len(rules)})", cls="mb-4"),
        (
            Grid(*[rule_display(r) for r in rules], cols_lg=2)
            if rules
            else P(
                "No rules defined, so every message sent to the topic is delivered.",
                cls=TextPresets.muted_sm,
            )
        ),
        cls="mb-8",
    )


@rt(
    "/configs/{configId}/namespaces/{namespace}/topics/{topic}/subscriptions/{subscription}"
)
def get(configId: int, namespace: str, topic: str, subscription: str, request=None):
    try:
        rules = subscription_rules(configId, namespace, topic, subscription)
        with connection.get_subscription_receiver(
            topic_name=topic, subscription_name=subscription
        ) as active_receiver:
            with connection.get_subscription_receiver(
                topic_name=topic, subscription_name=f"{subscription}/$deadletterqueue"
            ) as deadlettered_receiver:
                active_peeked_messages = active_receiver.peek_messages(
                    max_message_count=10
                )
                deadlettered_peeked_messages = deadlettered_receiver.peek_messages(
                    max_message_count=10
                )
                return _create_page(
                    Container(
                        H3(f"{namespace} > {topic} > {subscription}", cls="mb-8"),
                        rules_display(rules),
                        Grid(
                            Div(
                                H4("Active Messages", cls="mb-8"),
                                *[
                                    active_message_display(
                                        namespace, topic, subscription, x
                                    )
                                    for x in active_peeked_messages
                                ],
                                hx_get=f"/configs/{configId}/namespaces/{namespace}/topics/{topic}/subscriptions/{subscription}/active",
                                hx_trigger="every 2s",
                                hx_target="#active-messages-col",
                                hx_swap="outerHTML",
                                id="active-messages-col",
                            ),
                            Div(
                                H4("Dead Lettered Messages", cls="mb-8"),
                                *[
                                    deadlettered_message_display(
                                        namespace, topic, subscription, x
                                    )
                                    for x in deadlettered_peeked_messages
                                ],
                                hx_get=f"/configs/{configId}/namespaces/{namespace}/topics/{topic}/subscriptions/{subscription}/deadlettered",
                                hx_trigger="every 2s",
                                hx_target="#dead-lettered-messages-col",
                                hx_swap="outerHTML",
                                id="dead-lettered-messages-col",
                            ),
                            Div(H4("View"), id="enlarged-message"),
                        ),
                    ),
                    request,
                    configId,
                )
    except Exception as e:
        return Toast(
            DivLAligned(
                UkIcon("square-x", cls="mr-2"), f"Failed to load subscription: {e}"
            ),
            id="error-toast",
            dur=7,
            alert_cls=AlertT.error,
            cls=(ToastHT.end, ToastVT.bottom),
        )


@rt(
    "/configs/{configId}/namespaces/{namespace}/topics/{topic}/subscriptions/{subscription}/active"
)
def get(configId: int, namespace: str, topic: str, subscription: str):
    with connection.get_subscription_receiver(
        topic_name=topic, subscription_name=subscription
    ) as receiver:
        peeked_messages = receiver.peek_messages(max_message_count=100)
        return Div(
            H4("Active Messages", cls="mb-8"),
            *[
                active_message_display(namespace, topic, subscription, x)
                for x in peeked_messages
            ],
            hx_get=f"/configs/{configId}/namespaces/{namespace}/topics/{topic}/subscriptions/{subscription}/active",
            hx_trigger="every 2s",
            hx_target="#active-messages-col",
            hx_swap="outerHTML",
            id="active-messages-col",
        )


@rt(
    "/configs/{configId}/namespaces/{namespace}/topics/{topic}/subscriptions/{subscription}/deadlettered"
)
def get(configId: int, namespace: str, topic: str, subscription: str):
    with connection.get_subscription_receiver(
        topic_name=topic, subscription_name=f"{subscription}/$deadletterqueue"
    ) as receiver:
        peeked_messages = receiver.peek_messages(max_message_count=100)
        return Div(
            H4("Dead Lettered Messages", cls="mb-8"),
            *[
                deadlettered_message_display(namespace, topic, subscription, x)
                for x in peeked_messages
            ],
            hx_get=f"/configs/{configId}/namespaces/{namespace}/topics/{topic}/subscriptions/{subscription}/deadlettered",
            hx_trigger="every 2s",
            hx_target="#dead-lettered-messages-col",
            hx_swap="outerHTML",
            id="dead-lettered-messages-col",
        )


# Queue message routes
@rt("/{namespace}/{queue}/messages/active/{message_sequence_number}")
def get(namespace: str, queue: str, message_sequence_number: int):
    return larger_queue_message_display(namespace, queue, message_sequence_number)


@rt("/{namespace}/{queue}/messages/deadlettered/{message_sequence_number}")
def get(namespace: str, queue: str, message_sequence_number: int):
    return larger_queue_message_display(
        namespace, f"{queue}/$deadletterqueue", message_sequence_number
    )


# delete an active message from a queue
@rt("/{namespace}/{queue}/messages/active/{message_sequence_number}/delete")
def delete(namespace: str, queue: str, message_sequence_number: int):
    """Delete an active message from a queue"""
    with connection.get_queue_receiver(queue_name=queue, max_wait_time=5) as receiver:
        success, error = delete_message_by_sequence(receiver, message_sequence_number)

        if success:
            return (
                Div(H4("View"), id="enlarged-message"),
                Toast(
                    DivLAligned(
                        UkIcon("check-circle", cls="mr-2"),
                        "Message deleted successfully",
                    ),
                    id="success-toast",
                    dur=2,
                    alert_cls=AlertT.success,
                    cls=(ToastHT.end, ToastVT.bottom),
                ),
            )
        else:
            return Toast(
                DivLAligned(
                    UkIcon("square-x", cls="mr-2"), f"Failed to delete: {error}"
                ),
                id="error-toast",
                dur=5,
                alert_cls=AlertT.error,
                cls=(ToastHT.end, ToastVT.bottom),
            )


# delete a dead-lettered message from a queue
@rt("/{namespace}/{queue}/messages/deadlettered/{message_sequence_number}/delete")
def delete(namespace: str, queue: str, message_sequence_number: int):
    """Delete a dead-lettered message from a queue"""
    with connection.get_queue_receiver(
        queue_name=f"{queue}/$deadletterqueue", max_wait_time=5
    ) as receiver:
        success, error = delete_message_by_sequence(receiver, message_sequence_number)

        if success:
            return (
                Div(H4("View"), id="enlarged-message"),
                Toast(
                    DivLAligned(
                        UkIcon("check-circle", cls="mr-2"),
                        "Dead-lettered message deleted successfully",
                    ),
                    id="success-toast",
                    dur=2,
                    alert_cls=AlertT.success,
                    cls=(ToastHT.end, ToastVT.bottom),
                ),
            )
        else:
            return Toast(
                DivLAligned(
                    UkIcon("square-x", cls="mr-2"), f"Failed to delete: {error}"
                ),
                id="error-toast",
                dur=5,
                alert_cls=AlertT.error,
                cls=(ToastHT.end, ToastVT.bottom),
            )


def larger_queue_message_display(
    namespace: str, queue: str, message_sequence_number: int
):
    # Determine if this is a dead letter message
    is_dead_letter = queue.endswith("/$deadletterqueue")
    original_queue = queue.replace("/$deadletterqueue", "") if is_dead_letter else queue
    message_type = "deadlettered" if is_dead_letter else "active"

    with connection.get_queue_receiver(queue_name=queue) as receiver:
        peeked_message = receiver.peek_messages(
            max_message_count=1, sequence_number=message_sequence_number
        )[0]
        return (
            Div(
                H4("View", cls="mb-8"),
                H5("Message ID", cls="my-2"),
                P(peeked_message.message_id),
                H5("Content type", cls="my-2"),
                P(peeked_message.content_type),
                H5("Body", cls="my-2"),
                Pre(
                    format_message_body(peeked_message.body),
                    cls="overflow-auto max-h-96",
                ),
                H5("Headers", cls="my-2"),
                Table(
                    Tr(Th("key"), Th("Value")),
                    *[
                        Tr(Td(message_to_string(k)), Td(message_to_string(v)))
                        for k, v in (
                            peeked_message.application_properties.items()
                            if peeked_message.application_properties
                            else []
                        )
                    ],
                ),
                # Delete button and modal
                Div(
                    Button(
                        "Delete Message",
                        type="button",
                        data_uk_toggle=f"target: #delete-queue-message-modal-{message_sequence_number}",
                        cls=(ButtonT.destructive, "mt-8"),
                    ),
                    Modal(
                        ModalTitle("Confirm Delete"),
                        P(
                            "Are you sure you want to delete this message? This action cannot be undone.",
                            cls="my-4",
                        ),
                        footer=Div(
                            ModalCloseButton("Cancel", cls=ButtonT.secondary),
                            Button(
                                "Delete",
                                hx_delete=f"/{namespace}/{original_queue}/messages/{message_type}/{message_sequence_number}/delete",
                                hx_target="#enlarged-message",
                                hx_swap="outerHTML",
                                hx_on__after_request=f"UIkit.modal('#delete-queue-message-modal-{message_sequence_number}').hide()",
                                cls=ButtonT.destructive,
                            ),
                            cls="flex gap-2",
                        ),
                        id=f"delete-queue-message-modal-{message_sequence_number}",
                    ),
                    cls="mt-8",
                ),
                id="enlarged-message",
            ),
        )


@rt("/configs/{configId}/namespaces/{namespace}/queues/{queue}/active")
def get(configId: int, namespace: str, queue: str):
    with connection.get_queue_receiver(queue_name=queue) as receiver:
        peeked_messages = receiver.peek_messages(max_message_count=100)
        return Div(
            H4("Active Messages", cls="mb-8"),
            *[
                queue_message_display(namespace, queue, x, "active")
                for x in peeked_messages
            ],
            hx_get=f"/configs/{configId}/namespaces/{namespace}/queues/{queue}/active",
            hx_trigger="every 2s",
            hx_target="#active-messages-col",
            hx_swap="outerHTML",
            id="active-messages-col",
        )


@rt("/configs/{configId}/namespaces/{namespace}/queues/{queue}/deadlettered")
def get(configId: int, namespace: str, queue: str):
    with connection.get_queue_receiver(
        queue_name=f"{queue}/$deadletterqueue"
    ) as receiver:
        peeked_messages = receiver.peek_messages(max_message_count=100)
        return Div(
            H4("Dead Lettered Messages", cls="mb-8"),
            *[
                queue_message_display(namespace, queue, x, "deadlettered")
                for x in peeked_messages
            ],
            hx_get=f"/configs/{configId}/namespaces/{namespace}/queues/{queue}/deadlettered",
            hx_trigger="every 2s",
            hx_target="#dead-lettered-messages-col",
            hx_swap="outerHTML",
            id="dead-lettered-messages-col",
        )


async def active_messages(
    namespace: str, entity: str, subscription: str, seqNumber: int
):
    sn = seqNumber + 1 if seqNumber >= 0 else 0
    while True:  # need some sort of shutdown I think ?
        with connection.get_subscription_receiver(
            topic_name=entity, subscription_name=subscription
        ) as receiver:
            peeked_messages = receiver.peek_messages(
                max_message_count=10, sequence_number=sn
            )
            for m in peeked_messages:
                data = active_message_display(m)
                sn = m.sequence_number + 1
                yield sse_message(data, event="active-m")
            await asyncio.sleep(1)


@rt("/{namespace}/{entity}/{subscription}/active/{seqNumber}")
def get(namespace: str, entity: str, subscription: str, seqNumber: int):
    return EventStream(active_messages(namespace, entity, subscription, seqNumber))


@rt("/configs/{configId}/namespaces/{namespace}/queues/{queue}/send")
def get(configId: int, namespace: str, queue: str, request=None):
    return _create_page(
        Container(
            Modal(
                ModalTitle("Select a name for your saved message"),
                Form(
                    LabelInput("Name", id="formName"),
                    Button(
                        "Save",
                        type="submit",
                        cls=ButtonT.primary,
                    ),
                    hx_post=f"/{namespace}/{queue}/send/save",
                    hx_include="#send-message-form",
                    hx_target="#saved-sent-messages-container",
                    hx_swap="outerHTML",
                    hx_on__after_request="UIkit.modal('#save-message-modal').hide()",
                ),
                footer=Div(ModalCloseButton("Close", cls=ButtonT.secondary)),
                id="save-message-modal",
            ),
            Div(cls="space-y-4")(
                DivCentered(
                    H3("Send Message"),
                    P(f"To {namespace} - {queue} (Queue)", cls=TextPresets.muted_sm),
                ),
                send_message_form(
                    namespace, queue, post_url=f"/{namespace}/{queue}/queue/send"
                ),
                prev_saved_cards(namespace, queue),
            ),
        ),
        request,
        config_id=configId,
    )


@rt("/configs/{configId}/namespaces/{namespace}/queues/{queue}")
def get(configId: int, namespace: str, queue: str, request=None):
    try:
        with connection.get_queue_receiver(queue_name=queue) as active_receiver:
            with connection.get_queue_receiver(
                queue_name=f"{queue}/$deadletterqueue"
            ) as deadlettered_receiver:
                active_peeked_messages = active_receiver.peek_messages(
                    max_message_count=10
                )
                deadlettered_peeked_messages = deadlettered_receiver.peek_messages(
                    max_message_count=10
                )
                return _create_page(
                    Container(
                        H3(f"{namespace} > {queue} (Queue)", cls="mb-8"),
                        Grid(
                            Div(
                                H4("Active Messages", cls="mb-8"),
                                *[
                                    queue_message_display(namespace, queue, x, "active")
                                    for x in active_peeked_messages
                                ],
                                hx_get=f"/configs/{configId}/namespaces/{namespace}/queues/{queue}/active",
                                hx_trigger="every 2s",
                                hx_target="#active-messages-col",
                                hx_swap="outerHTML",
                                id="active-messages-col",
                            ),
                            Div(
                                H4("Dead Lettered Messages", cls="mb-8"),
                                *[
                                    queue_message_display(
                                        namespace, queue, x, "deadlettered"
                                    )
                                    for x in deadlettered_peeked_messages
                                ],
                                hx_get=f"/configs/{configId}/namespaces/{namespace}/queues/{queue}/deadlettered",
                                hx_trigger="every 2s",
                                hx_target="#dead-lettered-messages-col",
                                hx_swap="outerHTML",
                                id="dead-lettered-messages-col",
                            ),
                            Div(H4("View"), id="enlarged-message"),
                        ),
                    ),
                    request,
                    configId,
                )
    except Exception as e:
        return Toast(
            DivLAligned(UkIcon("square-x", cls="mr-2"), f"Failed to load queue: {e}"),
            id="error-toast",
            dur=7,
            alert_cls=AlertT.error,
            cls=(ToastHT.end, ToastVT.bottom),
        )


@rt("/{namespace}/{queue}")
def get(namespace: str, queue: str, request=None):
    return _create_page(
        Container(Div(f"{namespace} > {queue}")),
        request,
    )


def message_header_row(index: int, key: str = "", ct: str = "String", val: str = ""):
    return Grid(
        LabelInput("Key", id=f"hk{index}", value=key, name="messagePropertyKeys"),
        LabelSelect(
            Option("Select Content Type", selected=True, disabled=True),
            *[Option(e) for e in messagePropertyTypes.keys()],
            label="Type",
            name="messagePropertyContentTypes",
            id="messagePropertyContentTypes",
            value=ct,
        ),
        LabelInput("Value", id=f"hv{index}", value=val, name="messagePropertyValues"),
        Div(
            Button(
                "Remove",
                hx_get="/elements/blank",
                hx_swap="delete",
                hx_target=f"#mh{index}",
                cls=f"{ButtonT.destructive if index != 0 else 'hidden'} mt-auto",
            ),
            cls="flex",
        ),
        id=f"mh{index}",
    )


def is_htmx(request=None):
    "Check if the request is an HTMX request"
    return request and "hx-request" in request.headers


def _create_page(
    content,  # The content to display (without the layout/sidebar)
    request,  # Request object to determine if HTMX request
    config_id: int | None = None,  # Optional namespaces for sidebar
):
    "Makes page load sidebar if direct request, otherwise loads content only via HTMX"
    if is_htmx(request):
        return content
    else:
        return with_layout(content, config_id)


def with_layout(content, config_id: int | None = None):
    "Puts the sidebar and content into a layout"
    return Title("SB Explorer"), Div(cls="flex flex-col md:flex-row w-full")(
        Div(cls="md:flex w-full")(
            Div(sidebar(config_id), cls="hidden md:block w-1/4 "),  # max-w-80
            Div(
                content,
                cls="md:w-3/4 w-full mr-5",
                id="content",
            ),
        ),
    )


def load_namespaces(config_id: int) -> list[Namespace]:
    "Parse the namespaces from a saved configuration file"
    with open(configs[config_id].path) as f:
        return Configuration.model_validate_json(f.read()).UserConfig.Namespaces


def sidebar(config_id: int | None):
    namespaces = load_namespaces(config_id) if config_id is not None else []

    def create_li(title, href):
        return Li(A(title, hx_target="#content", hx_get=href, hx_push_url="true"))

    return NavContainer(
        NavHeaderLi(A("Home", hx_target="#content", hx_get="/", hx_push_url="true")),
        NavParentLi(
            (
                A(
                    DivFullySpaced(
                        "Namespaces",
                    )
                )
                if namespaces
                else Div()
            ),
            NavContainer(
                *[
                    NavParentLi(
                        A(n.Name, cls="uk-open"),
                        NavContainer(
                            NavContainer(
                                *[
                                    NavParentLi(
                                        A(
                                            DivFullySpaced(
                                                "Topics",
                                            )
                                        ),
                                        NavContainer(
                                            *[
                                                NavParentLi(
                                                    A(x.Name, cls="uk-open"),
                                                    NavContainer(
                                                        create_li(
                                                            "Send",
                                                            f"/configs/{config_id}/namespaces/{n.Name}/topics/{x.Name}/send",
                                                        ),
                                                        NavParentLi(
                                                            A(
                                                                DivFullySpaced(
                                                                    "Subscriptions",
                                                                )
                                                            ),
                                                            NavContainer(
                                                                *[
                                                                    create_li(
                                                                        z.Name,
                                                                        f"/configs/{config_id}/namespaces/{n.Name}/topics/{x.Name}/subscriptions/{z.Name}",
                                                                    )
                                                                    for z in x.Subscriptions
                                                                ],
                                                                parent=False,
                                                                uk_nav=True,
                                                            ),
                                                            cls="uk-open",
                                                        ),
                                                        parent=False,
                                                        uk_nav=True,
                                                    ),
                                                    cls="uk-open",
                                                )
                                                for x in n.Topics
                                            ],
                                            parent=False,
                                            uk_nav=True,
                                        ),
                                        cls="uk-open",
                                    )
                                ],
                                parent=False,
                                uk_nav=True,
                            ),
                            NavContainer(
                                *[
                                    NavParentLi(
                                        A(
                                            DivFullySpaced(
                                                "Queues",
                                            )
                                        ),
                                        NavContainer(
                                            *[
                                                NavParentLi(
                                                    A(x.Name, cls="uk-open"),
                                                    NavContainer(
                                                        create_li(
                                                            "Send",
                                                            f"/configs/{config_id}/namespaces/{n.Name}/queues/{x.Name}/send",
                                                        ),
                                                        create_li(
                                                            "View",
                                                            f"/configs/{config_id}/namespaces/{n.Name}/queues/{x.Name}",
                                                        ),
                                                        parent=False,
                                                        uk_nav=True,
                                                    ),
                                                    cls="uk-open",
                                                )
                                                for x in n.Queues
                                            ],
                                            parent=False,
                                            uk_nav=True,
                                        ),
                                        cls="uk-open",
                                    )
                                ],
                                parent=False,
                                uk_nav=True,
                            ),
                            cls="uk-open",
                        ),
                        cls="uk-open",
                    )
                    for n in namespaces
                ],
                parent=False,
                uk_nav=True,
            ),
            cls="uk-open",
        ),
        cls=("thesidebar", NavT.primary, "space-y-4 p-4 w-full md:w-full"),
    )


try:
    serve()
finally:
    if connection is not None:
        connection.close()
