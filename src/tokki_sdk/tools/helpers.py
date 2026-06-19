"""Thin helpers for constructing ToolResultContent protos."""

from tokki_sdk.tokki_pb2 import (
    Attachment,
    ContentNode,
    ToolResultContent,
    ToolResultContentNode,
    TextContent,
)


def text_result(text: str) -> ToolResultContent:
    """Create a text-only tool result."""
    return ToolResultContent(nodes=[ToolResultContentNode(text=TextContent(text=text))])


def error_result(message: str) -> ToolResultContent:
    """Create an error tool result."""
    return ToolResultContent(nodes=[ToolResultContentNode(text=TextContent(text=message))], is_error=True)


def tool_result_node_to_content_node(node: ToolResultContentNode) -> ContentNode:
    """Convert a ToolResultContentNode to a ContentNode."""
    which = node.WhichOneof("content")
    if which == "text":
        return ContentNode(text=node.text.text)
    elif which == "image":
        return ContentNode(
            attachment=Attachment(
                mime_type=node.image.mime_type,
                data=bytes(node.image.data, "utf-8"),
            )
        )
    elif which == "audio":
        return ContentNode(
            attachment=Attachment(
                mime_type=node.audio.mime_type,
                data=bytes(node.audio.data, "utf-8"),
            )
        )
    elif which == "resource_link":
        rl = node.resource_link
        return ContentNode(
            attachment=Attachment(
                mime_type=rl.mime_type or "",
                name=rl.name,
                description=rl.description,
                url=rl.uri,
            )
        )
    elif which == "embedded_resource":
        er = node.embedded_resource
        return ContentNode(
            attachment=Attachment(
                mime_type=er.mime_type or "",
                url=er.uri,
                data=er.blob if er.blob else bytes(er.text or "", "utf-8"),
            )
        )
    else:
        return ContentNode(text=str(node))
