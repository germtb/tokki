"""
PDF generation tool.

Converts markdown content to a PDF file using WeasyPrint.
"""

import os
from pathlib import Path

from tokki_sdk.tokki_pb2 import ToolResultContent, ToolResultContentNode, TextContent, ResourceLink
from .base import Tool, ToolError


class PdfTool(Tool):
    """
    Tool for converting markdown to PDF.

    The generated PDF is saved to the workspace and a resource link is returned
    that can be used to fetch the file via the backend's /files endpoint.
    """

    @property
    def name(self) -> str:
        return "pdf"

    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "pdf",
                "description": "Convert markdown content to a PDF file. Returns a link to download the generated PDF.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "markdown": {
                            "type": "string",
                            "description": "The markdown content to convert to PDF",
                        },
                        "filename": {
                            "type": "string",
                            "description": "Output filename (without .pdf extension). Defaults to 'output'",
                        },
                        "title": {
                            "type": "string",
                            "description": "Document title for the PDF metadata",
                        },
                    },
                    "required": ["markdown"],
                },
            },
        }

    async def execute(self, input: dict):
        markdown_content = input.get("markdown")
        if not markdown_content:
            raise ToolError("markdown content is required")

        filename = input.get("filename", "output")
        if not filename.endswith(".pdf"):
            filename = f"{filename}.pdf"

        title = input.get("title", "Generated Document")


        # Import dependencies here to allow graceful failure if not installed
        try:
            import markdown  # type: ignore[import-untyped]
            from weasyprint import HTML, CSS  # type: ignore[import-not-found]
        except ImportError as e:
            raise ToolError(
                f"PDF generation requires 'markdown' and 'weasyprint' packages. "
                f"Install with: pip install markdown weasyprint. Error: {e}"
            )

        # Convert markdown to HTML
        html_content = markdown.markdown(
            markdown_content,
            extensions=["tables", "fenced_code", "codehilite", "toc"],
        )

        # Wrap in a full HTML document with styling
        full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
</head>
<body>
{html_content}
</body>
</html>
"""

        # Basic CSS for nice PDF output
        css = CSS(
            string="""
            @page {
                size: A4;
                margin: 2cm;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                font-size: 12pt;
                line-height: 1.6;
                color: #333;
            }
            h1 { font-size: 24pt; margin-top: 0; color: #111; }
            h2 { font-size: 18pt; color: #222; }
            h3 { font-size: 14pt; color: #333; }
            code {
                font-family: 'SF Mono', Monaco, 'Courier New', monospace;
                background-color: #f5f5f5;
                padding: 2px 4px;
                border-radius: 3px;
                font-size: 10pt;
            }
            pre {
                background-color: #f5f5f5;
                padding: 12px;
                border-radius: 6px;
                overflow-x: auto;
            }
            pre code {
                background-color: transparent;
                padding: 0;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 1em 0;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #f5f5f5;
            }
            blockquote {
                border-left: 4px solid #ddd;
                margin: 1em 0;
                padding-left: 1em;
                color: #666;
            }
            a {
                color: #0066cc;
            }
        """
        )

        # Generate PDF
        output_path = self.context.resolve_path(filename)

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            html = HTML(string=full_html)
            html.write_pdf(output_path, stylesheets=[css])
        except Exception as e:
            raise ToolError(f"Failed to generate PDF: {e}")

        # Get file size
        file_size = output_path.stat().st_size

        # Construct the resource link URL
        # Use workspace-relative path - the serving layer (CLI or backend) will resolve
        # based on the session context
        workspace_absolute = self.context.workspace_dir.resolve()
        relative_path = output_path.relative_to(workspace_absolute)
        resource_uri = f"/workspace/{relative_path}"

        text_node = ToolResultContentNode(
            text=TextContent(
                text=f"Successfully created PDF: {filename} ({file_size} bytes). "
                "A download link is automatically provided to the user."
            )
        )
        link_node = ToolResultContentNode(
            resource_link=ResourceLink(
                uri=resource_uri,
                name=filename,
                title=title or "",
                mime_type="application/pdf",
                size=file_size,
            )
        )

        return ToolResultContent(nodes=[text_node, link_node])
