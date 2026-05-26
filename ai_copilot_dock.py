import os
import re
from PyQt6.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                             QPushButton, QLabel, QScrollArea, QFrame, QTextBrowser, 
                             QGraphicsDropShadowEffect, QSizePolicy)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThreadPool, QSize
from ai_worker import AICopilotWorker
import ai_tools

def parse_inline_markdown(text):
    """Parses standard bold, italic, and inline code formatting."""
    # Bold: **bold**
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    # Italic: *italic*
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text)
    # Inline code: `code`
    text = re.sub(r'`(.*?)`', r'<code style="background-color: #edf2f7; color: #c7254e; padding: 2px 4px; border-radius: 3px; font-family: monospace; font-size: 11px;">\1</code>', text)
    return text

def build_html_table(rows):
    """Translates Markdown tabular lines into a premium styled HTML table."""
    html = []
    html.append('<table style="border-collapse: collapse; width: 100%; border: 1px solid #cbd5e1; margin: 8px 0; font-size: 11px; font-family: \'Segoe UI\', sans-serif;">')
    
    for idx, r in enumerate(rows):
        cells = [c.strip() for c in r.split("|")]
        # Remove empty outer items
        if cells and not cells[0]:
            cells = cells[1:]
        if cells and not cells[-1]:
            cells = cells[:-1]
            
        bg = "#ffffff"
        font_weight = "normal"
        color = "#1e293b"
        
        if idx == 0:
            # Header Row
            bg = "#2e7d32"  # Standard Estimator Pro Green
            font_weight = "bold"
            color = "#ffffff"
            tag = "th"
        else:
            tag = "td"
            if idx % 2 == 0:
                bg = "#f1f8e9"  # Light green zebra shading
                
        html.append(f'<tr style="background-color: {bg}; color: {color};">')
        for cell in cells:
            cell_parsed = parse_inline_markdown(cell)
            padding = "6px 8px" if idx == 0 else "5px 8px"
            border = "1px solid #cbd5e1"
            html.append(f'<{tag} style="padding: {padding}; border: {border}; text-align: left; font-weight: {font_weight};">{cell_parsed}</{tag}>')
        html.append('</tr>')
        
    html.append('</table>')
    return "\n".join(html)

def markdown_to_html(text):
    """Converts a subset of Markdown (headings, lists, blockquotes/alerts, code blocks, tables) to rich HTML."""
    # Escape HTML tags first to prevent code blocks from parsing as real HTML
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    lines = text.split("\n")
    html_lines = []
    
    in_code = False
    code_block = []
    
    in_table = False
    table_rows = []
    
    in_list = False
    
    in_quote = False
    quote_type = "general"
    quote_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Handle code blocks
        if line.strip().startswith("```"):
            if in_code:
                code_content = "\n".join(code_block)
                html_lines.append(f'<pre style="background-color: #1e293b; color: #f8fafc; padding: 10px; border-radius: 6px; font-family: Consolas, Monaco, monospace; font-size: 11px; white-space: pre-wrap; margin: 8px 0;">{code_content}</pre>')
                in_code = False
                code_block = []
            else:
                in_code = True
            i += 1
            continue
            
        if in_code:
            code_block.append(line)
            i += 1
            continue
            
        # Handle blockquotes/alerts (escaped > is &gt;)
        stripped = line.strip()
        if stripped.startswith("&gt;"):
            in_quote = True
            quote_line = stripped[4:].strip()
            
            if "[!NOTE]" in quote_line:
                quote_type = "note"
                quote_line = quote_line.replace("[!NOTE]", "").strip()
            elif "[!THINK]" in quote_line:
                quote_type = "think"
                quote_line = quote_line.replace("[!THINK]", "").strip()
            elif "[!TIP]" in quote_line:
                quote_type = "tip"
                quote_line = quote_line.replace("[!TIP]", "").strip()
            elif "[!WARNING]" in quote_line:
                quote_type = "warning"
                quote_line = quote_line.replace("[!WARNING]", "").strip()
            elif "[!CAUTION]" in quote_line:
                quote_type = "caution"
                quote_line = quote_line.replace("[!CAUTION]", "").strip()
            elif "[!IMPORTANT]" in quote_line:
                quote_type = "important"
                quote_line = quote_line.replace("[!IMPORTANT]", "").strip()
                
            if quote_line:
                quote_lines.append(quote_line)
            i += 1
            continue
        elif in_quote:
            if quote_lines:
                quote_text = " ".join(quote_lines)
                quote_text = parse_inline_markdown(quote_text)
                
                if quote_type == "note":
                    html_lines.append(f'<div style="border-left: 4px solid #2196f3; background-color: #e3f2fd; padding: 8px 10px; margin: 8px 0; border-radius: 4px; color: #0d47a1;"><b>ℹ️ Note</b><br/>{quote_text}</div>')
                elif quote_type == "think":
                    html_lines.append(f'<div style="border-left: 4px solid #8b5cf6; background-color: #f5f3ff; padding: 8px 10px; margin: 8px 0; border-radius: 4px; color: #5b21b6; font-style: italic;"><b>🧠 Thought Process</b><br/>{quote_text}</div>')
                elif quote_type == "tip":
                    html_lines.append(f'<div style="border-left: 4px solid #4caf50; background-color: #e8f5e9; padding: 8px 10px; margin: 8px 0; border-radius: 4px; color: #1b5e20;"><b>💡 Tip</b><br/>{quote_text}</div>')
                elif quote_type in ["warning", "caution"]:
                    html_lines.append(f'<div style="border-left: 4px solid #ff9800; background-color: #fff3e0; padding: 8px 10px; margin: 8px 0; border-radius: 4px; color: #e65100;"><b>⚠️ Warning</b><br/>{quote_text}</div>')
                elif quote_type == "important":
                    html_lines.append(f'<div style="border-left: 4px solid #9c27b0; background-color: #f3e5f5; padding: 8px 10px; margin: 8px 0; border-radius: 4px; color: #4a148c;"><b>🔔 Important</b><br/>{quote_text}</div>')
                else:
                    html_lines.append(f'<div style="border-left: 4px solid #94a3b8; background-color: #f8fafc; padding: 8px 10px; margin: 8px 0; border-radius: 4px; color: #334155; font-style: italic;">{quote_text}</div>')
            in_quote = False
            quote_lines = []
            quote_type = "general"
            
        # Handle tables
        if line.strip().startswith("|"):
            in_table = True
            if "---" in line:
                i += 1
                continue
            table_rows.append(line)
            i += 1
            continue
        elif in_table:
            if table_rows:
                html_lines.append(build_html_table(table_rows))
            in_table = False
            table_rows = []
            
        # Handle bullet lists
        if line.strip().startswith("- ") or line.strip().startswith("* ") or line.strip().startswith("• "):
            if not in_list:
                html_lines.append('<ul style="margin: 4px 0; padding-left: 20px;">')
                in_list = True
            list_item = line.strip()[2:]
            html_lines.append(f'<li style="margin: 2px 0;">{parse_inline_markdown(list_item)}</li>')
            i += 1
            continue
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
                
        # Normal paragraphs & headings
        line_stripped = line.strip()
        if not line_stripped:
            i += 1
            continue
            
        if line_stripped.startswith("### "):
            html_lines.append(f'<h4 style="color: #2e7d32; margin-top: 6px; margin-bottom: 2px; font-size: 13px; font-weight: bold;">{parse_inline_markdown(line_stripped[4:])}</h4>')
        elif line_stripped.startswith("## "):
            html_lines.append(f'<h3 style="color: #2e7d32; margin-top: 8px; margin-bottom: 3px; font-size: 14px; border-bottom: 1px solid #cbd5e1; padding-bottom: 2px; font-weight: bold;">{parse_inline_markdown(line_stripped[3:])}</h3>')
        elif line_stripped.startswith("# "):
            html_lines.append(f'<h2 style="color: #1b5e20; margin-top: 10px; margin-bottom: 4px; font-size: 16px; border-bottom: 2px solid #2e7d32; padding-bottom: 4px; font-weight: bold;">{parse_inline_markdown(line_stripped[2:])}</h2>')
        else:
            html_lines.append(f'<p style="margin: 2px 0; line-height: 1.3;">{parse_inline_markdown(line_stripped)}</p>')
            
        i += 1
        
    # Flush trailing blocks
    if in_quote and quote_lines:
        quote_text = " ".join(quote_lines)
        quote_text = parse_inline_markdown(quote_text)
        if quote_type == "note":
            html_lines.append(f'<div style="border-left: 4px solid #2196f3; background-color: #e3f2fd; padding: 8px 10px; margin: 8px 0; border-radius: 4px; color: #0d47a1;"><b>ℹ️ Note</b><br/>{quote_text}</div>')
        elif quote_type == "think":
            html_lines.append(f'<div style="border-left: 4px solid #8b5cf6; background-color: #f5f3ff; padding: 8px 10px; margin: 8px 0; border-radius: 4px; color: #5b21b6; font-style: italic;"><b>🧠 Thought Process</b><br/>{quote_text}</div>')
        elif quote_type == "tip":
            html_lines.append(f'<div style="border-left: 4px solid #4caf50; background-color: #e8f5e9; padding: 8px 10px; margin: 8px 0; border-radius: 4px; color: #1b5e20;"><b>💡 Tip</b><br/>{quote_text}</div>')
        elif quote_type in ["warning", "caution"]:
            html_lines.append(f'<div style="border-left: 4px solid #ff9800; background-color: #fff3e0; padding: 8px 10px; margin: 8px 0; border-radius: 4px; color: #e65100;"><b>⚠️ Warning</b><br/>{quote_text}</div>')
        elif quote_type == "important":
            html_lines.append(f'<div style="border-left: 4px solid #9c27b0; background-color: #f3e5f5; padding: 8px 10px; margin: 8px 0; border-radius: 4px; color: #4a148c;"><b>🔔 Important</b><br/>{quote_text}</div>')
        else:
            html_lines.append(f'<div style="border-left: 4px solid #94a3b8; background-color: #f8fafc; padding: 8px 10px; margin: 8px 0; border-radius: 4px; color: #334155; font-style: italic;">{quote_text}</div>')
            
    if in_table and table_rows:
        html_lines.append(build_html_table(table_rows))
        
    if in_list:
        html_lines.append("</ul>")
        
    return "\n".join(html_lines)


class ChatInputEdit(QTextEdit):
    """Custom QTextEdit capturing standard Return keys to send, while allowing Shift+Return for newlines,
    and dynamically adjusting its height to fit the content without vertical scrollbars."""
    enter_pressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.textChanged.connect(self.adjust_height)
        self.setFixedHeight(32)

    def adjust_height(self):
        doc = self.document()
        width = self.viewport().width()
        if width > 0:
            doc.setTextWidth(width)
        
        doc_height = doc.size().height()
        
        # Calculate optimal height with some padding to prevent truncation
        target_height = int(doc_height) + 8
        
        min_height = 32
        max_height = 150
        
        target_height = max(min_height, min(target_height, max_height))
        self.setFixedHeight(target_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_height()

    def keyPressEvent(self, event):
        if event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.enter_pressed.emit()
        else:
            super().keyPressEvent(event)



class MessageBubble(QFrame):
    """Representing an alternating message container with professional colors and drop shadows."""
    def __init__(self, text, is_ai=True, zoom_level=11, parent=None):
        super().__init__(parent)
        self.is_ai = is_ai
        self.zoom_level = zoom_level
        
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        
        if self.is_ai:
            self.setObjectName("AiBubble")
            self.setStyleSheet(f"""
                QFrame#AiBubble {{
                    background-color: #e8f5e9;
                    border: 1px solid #c8e6c9;
                    border-radius: 10px;
                }}
            """)
        else:
            self.setObjectName("UserBubble")
            self.setStyleSheet(f"""
                QFrame#UserBubble {{
                    background-color: #f1f5f9;
                    border: 1px solid #cbd5e1;
                    border-radius: 10px;
                }}
            """)
            
        # Add subtle graphic drop shadow for cards
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(6)
        shadow.setColor(QColor(0, 0, 0, 15))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(1)
        
        # Sender Header
        self.author_label = QLabel(self)
        if self.is_ai:
            self.author_label.setText("🤖 <b>AI Estimating Copilot</b>")
            self.author_label.setStyleSheet("color: #2e7d32; font-size: 10px; font-weight: bold; margin: 0px; padding: 0px;")
        else:
            self.author_label.setText("👤 <b>You</b>")
            self.author_label.setStyleSheet("color: #475569; font-size: 10px; font-weight: bold; margin: 0px; padding: 0px;")
        self.author_label.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.author_label)
        
        # Transparent Text Browser (permits selection, copying, and rendering of complex markup tables)
        self.text_browser = QTextBrowser(self)
        self.text_browser.setFrameShape(QFrame.Shape.NoFrame)
        self.text_browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_browser.viewport().setAutoFillBackground(False)
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.document().setDocumentMargin(0)
        self.update_font_size(self.zoom_level)
        
        self.html_content = markdown_to_html(text)
        self.text_browser.setHtml(self.html_content)
        layout.addWidget(self.text_browser)
        
        # Re-evaluate sizing to dynamic content size
        self.text_browser.document().contentsChanged.connect(self.adjust_browser_height)
        self.adjust_browser_height()
        
    def adjust_browser_height(self):
        doc = self.text_browser.document()
        doc.adjustSize()
        height = int(doc.size().height()) + 2
        self.text_browser.setFixedHeight(max(14, height))

    def update_font_size(self, size):
        self.zoom_level = size
        self.text_browser.setStyleSheet(f"""
            QTextBrowser {{
                background: transparent;
                background-color: transparent;
                border: none;
                margin: 0px;
                padding: 0px;
                color: #1e293b;
                font-family: "Segoe UI", sans-serif;
                font-size: {self.zoom_level}px;
            }}
        """)
        self.adjust_browser_height()


class TypingIndicator(QFrame):
    """Pulsing loading bubble to show the agent is actively calculating or querying APIs."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TypingIndicator")
        self.setStyleSheet("""
            QFrame#TypingIndicator {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 10px;
            }
        """)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(4)
        shadow.setColor(QColor(0, 0, 0, 10))
        shadow.setOffset(0, 1)
        self.setGraphicsEffect(shadow)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        
        self.label = QLabel("🤖 <i>Copilot is researching active database...</i>", self)
        self.label.setStyleSheet("color: #475569; font-size: 11px;")
        layout.addWidget(self.label)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_dots)
        self.dots = 0
        
    def start_animation(self):
        self.dots = 0
        self.timer.start(450)
        self.show()
        
    def stop_animation(self):
        self.timer.stop()
        self.hide()
        
    def animate_dots(self):
        self.dots = (self.dots + 1) % 4
        dots_str = "." * self.dots
        self.label.setText(f"🤖 <i>Copilot is researching active database{dots_str}</i>")


class AICopilotDock(QDockWidget):
    """Stunning, collapsible QDockWidget featuring a highly styled background QRunnable chat client."""
    def __init__(self, main_window, parent=None):
        super().__init__("AI Estimating Copilot", parent)
        self.main_window = main_window
        self.zoom_level = 11
        
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable | 
                         QDockWidget.DockWidgetFeature.DockWidgetFloatable | 
                         QDockWidget.DockWidgetFeature.DockWidgetMovable)
        
        self.setObjectName("AICopilotDock")
        self.setMinimumWidth(250)
        
        # Central Widget
        self.widget_container = QWidget(self)
        self.widget_container.setStyleSheet("background-color: #f8fafc;")
        self.setWidget(self.widget_container)
        
        # Layouts
        self.main_layout = QVBoxLayout(self.widget_container)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.setSpacing(4)
        
        # 1. Header Row
        self._setup_header()
        
        # 2. Context Indicator Box
        self._setup_context_box()
        
        # 3. Scrollable Message Box
        self._setup_scroll_area()
        
        # 4. Typing Indicator
        self.typing_indicator = TypingIndicator(self)
        self.main_layout.addWidget(self.typing_indicator)
        self.typing_indicator.hide()
        
        # 5. Input Text Panel
        self._setup_input_panel()
        
        # Initial Welcome Message
        welcome_text = (
            "# 👋 Welcome to Estimator Pro AI Copilot\\n\\n"
            "I am your intelligent, context-aware desktop estimating assistant. "
            "I have indexed your active SQL databases, cost libraries, and workspace files.\\n\\n"
            "### 💡 How can I assist you today?\\n"
            "Try asking me questions like:\\n"
            "- **\"Show active estimate KPIs\"**: Renders a beautiful summary dashboard of the current project.\\n"
            "- **\"Analyze project outliers\"**: Scans materials, labor, and plant rates against cost libraries to detect deviations exceeding ±15%.\\n"
            "- **\"Show workspace file structure\"**: Renders a complete directory tree of the project files.\\n"
            "- **\"Search historical rates for Concrete\"**: Queries `construction_rates.db` for pre-calculated pricing breakdowns."
        )
        welcome_text = welcome_text.replace("\\n", "\n")
        self.add_message_bubble(welcome_text, is_ai=True)
        
        # Context polling timer to automatically update the project context card
        self.context_timer = QTimer(self)
        self.context_timer.timeout.connect(self.update_active_context)
        self.context_timer.start(2500)
        self.update_active_context()

    def sizeHint(self):
        return QSize(330, 600)

    def _setup_header(self):
        header_widget = QWidget(self)
        header_widget.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #e2e8f0; border-radius: 4px;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(8, 4, 8, 4)
        
        title_label = QLabel("✨ <b>Copilot Chat</b>", self)
        title_label.setStyleSheet("color: #2e7d32; font-size: 12px;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Zoom In
        self.btn_zoom_in = QPushButton("A+", self)
        self.btn_zoom_in.setToolTip("Increase text size")
        self.btn_zoom_in.setFixedSize(24, 20)
        self.btn_zoom_in.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_zoom_in.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #475569;
                font-weight: bold;
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                font-size: 10px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                color: #2e7d32;
                border-color: #2e7d32;
            }
        """)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        header_layout.addWidget(self.btn_zoom_in)
        
        # Zoom Out
        self.btn_zoom_out = QPushButton("A-", self)
        self.btn_zoom_out.setToolTip("Decrease text size")
        self.btn_zoom_out.setFixedSize(24, 20)
        self.btn_zoom_out.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_zoom_out.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #475569;
                font-weight: bold;
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                font-size: 10px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                color: #2e7d32;
                border-color: #2e7d32;
            }
        """)
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        header_layout.addWidget(self.btn_zoom_out)
        
        # Clear Button
        self.btn_clear = QPushButton("🗑️", self)
        self.btn_clear.setToolTip("Clear conversation history")
        self.btn_clear.setFixedSize(24, 20)
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ef4444;
                border: 1px solid #fca5a5;
                border-radius: 3px;
                font-size: 10px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #fee2e2;
                color: #dc2626;
                border-color: #ef4444;
            }
        """)
        self.btn_clear.clicked.connect(self.clear_chat)
        header_layout.addWidget(self.btn_clear)
        
        self.main_layout.addWidget(header_widget)

    def _setup_context_box(self):
        self.context_card = QFrame(self)
        self.context_card.setObjectName("ContextCard")
        self.context_card.setStyleSheet("""
            QFrame#ContextCard {
                background-color: #e2e8f0;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
            }
        """)
        card_layout = QVBoxLayout(self.context_card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(2)
        
        self.context_title = QLabel("🔌 <b>Context Status</b>: Online", self)
        self.context_title.setStyleSheet("font-size: 10px; color: #1e293b; font-weight: bold;")
        card_layout.addWidget(self.context_title)
        
        self.context_details = QLabel("No active project detected.", self)
        self.context_details.setWordWrap(True)
        self.context_details.setStyleSheet("font-size: 9px; color: #475569;")
        card_layout.addWidget(self.context_details)
        
        self.main_layout.addWidget(self.context_card)

    def _setup_scroll_area(self):
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background-color: transparent;")
        
        self.chat_content_widget = QWidget()
        self.chat_content_widget.setStyleSheet("background-color: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_content_widget)
        self.chat_layout.setContentsMargins(2, 2, 2, 2)
        self.chat_layout.setSpacing(4)
        self.chat_layout.addStretch()
        
        self.scroll_area.setWidget(self.chat_content_widget)
        self.main_layout.addWidget(self.scroll_area, stretch=1)

    def _setup_input_panel(self):
        input_container = QWidget(self)
        input_container.setStyleSheet("background-color: #ffffff; border-top: 1px solid #e2e8f0; border-radius: 4px;")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(6, 6, 6, 6)
        input_layout.setSpacing(6)
        
        self.input_edit = ChatInputEdit(self)
        self.input_edit.setPlaceholderText("Ask about estimate outliers, workspace structure, rates...")
        self.input_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
                color: #1e293b;
            }
            QTextEdit:focus {
                border-color: #2e7d32;
            }
        """)
        self.input_edit.enter_pressed.connect(self.submit_query)
        input_layout.addWidget(self.input_edit, stretch=1, alignment=Qt.AlignmentFlag.AlignBottom)
        
        self.btn_send = QPushButton("Send", self)
        self.btn_send.setFixedSize(50, 32)
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        # Using premium standard green / yellow text highlight colors matching Estimator Pro design system
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: #ffff00;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #388e3c;
            }
            QPushButton:pressed {
                background-color: #1b5e20;
            }
        """)
        self.btn_send.clicked.connect(self.submit_query)
        input_layout.addWidget(self.btn_send, alignment=Qt.AlignmentFlag.AlignBottom)
        
        self.main_layout.addWidget(input_container)

    def add_message_bubble(self, text, is_ai=True):
        """Creates a MessageBubble widget, formats the text context, and scrolls to bottom."""
        # Insert bubble before the stretch placeholder
        bubble = MessageBubble(text, is_ai=is_ai, zoom_level=self.zoom_level, parent=self)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        
        # Force interface layout recalculation and scroll down smoothly
        QTimer.singleShot(100, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        vbar = self.scroll_area.verticalScrollBar()
        vbar.setValue(vbar.maximum())

    def zoom_in(self):
        self.zoom_level = min(18, self.zoom_level + 1)
        self._refresh_bubble_fonts()

    def zoom_out(self):
        self.zoom_level = max(8, self.zoom_level - 1)
        self._refresh_bubble_fonts()

    def _refresh_bubble_fonts(self):
        for i in range(self.chat_layout.count()):
            widget = self.chat_layout.itemAt(i).widget()
            if isinstance(widget, MessageBubble):
                widget.update_font_size(self.zoom_level)
        self.scroll_to_bottom()

    def clear_chat(self):
        """Removes all conversation bubbles from the scroll layout and re-adds the welcome card."""
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        welcome_text = (
            "# 👋 Welcome to Estimator Pro AI Copilot\\n\\n"
            "I am your intelligent, context-aware desktop estimating assistant. "
            "I have indexed your active SQL databases, cost libraries, and workspace files.\\n\\n"
            "### 💡 How can I assist you today?\\n"
            "Try asking me questions like:\\n"
            "- **\"Show active estimate KPIs\"**: Renders a beautiful summary dashboard of the current project.\\n"
            "- **\"Analyze project outliers\"**: Scans materials, labor, and plant rates against cost libraries to detect deviations exceeding ±15%.\\n"
            "- **\"Show workspace file structure\"**: Renders a complete directory tree of the project files.\\n"
            "- **\"Search historical rates for Concrete\"**: Queries `construction_rates.db` for pre-calculated pricing breakdowns."
        )
        welcome_text = welcome_text.replace("\\n", "\n")
        self.add_message_bubble(welcome_text, is_ai=True)

    def update_active_context(self):
        """Polls the workspace structure and MDI window details to update the context banner."""
        try:
            summary = ai_tools.query_active_estimate_summary(self.main_window)
            if "status" in summary:
                self.context_title.setText("🔌 <b>Context Status</b>: Online")
                self.context_details.setText("No active project editor selected. Using standard database libraries.")
            else:
                proj_name = summary.get("project_name") or "PBOQ Active Table"
                total_val = summary.get("grand_total") or 0.0
                currency = summary.get("currency") or "GHS"
                
                # Format a short overview of active window context
                if "total_boq_items" in summary:
                    # PBOQ active dialog
                    self.context_title.setText("🔌 <b>Context</b>: Active PBOQ Table")
                    self.context_details.setText(f"Items: {summary.get('total_boq_items')} | Plugs: {summary.get('plugged_items')}")
                else:
                    # Rate Build-up dialogue active
                    self.context_title.setText(f"🔌 <b>Context</b>: {proj_name}")
                    self.context_details.setText(f"Subtotal: {currency} {summary.get('subtotal', 0.0):,.2f} | Grand Total: {currency} {total_val:,.2f}")
        except Exception:
            self.context_title.setText("🔌 <b>Context Status</b>: Suspended")
            self.context_details.setText("Estimator workspace loading state...")

    def submit_query(self):
        query = self.input_edit.toPlainText().strip()
        if not query:
            return
            
        self.input_edit.clear()
        self.add_message_bubble(query, is_ai=False)
        
        # Spin up the background thread worker safely
        self.btn_send.setEnabled(False)
        self.typing_indicator.start_animation()
        
        if not hasattr(self, '_active_workers'):
            self._active_workers = set()
            
        worker = AICopilotWorker(query, main_window=self.main_window)
        self._active_workers.add(worker)
        
        def cleanup():
            self._active_workers.discard(worker)
            
        worker.signals.finished.connect(self.on_worker_finished)
        worker.signals.finished.connect(cleanup)
        worker.signals.error.connect(self.on_worker_error)
        worker.signals.error.connect(cleanup)
        
        QThreadPool.globalInstance().start(worker)

    def on_worker_finished(self, text):
        self.btn_send.setEnabled(True)
        self.typing_indicator.stop_animation()
        self.add_message_bubble(text, is_ai=True)

    def on_worker_error(self, error_msg):
        self.btn_send.setEnabled(True)
        self.typing_indicator.stop_animation()
        self.add_message_bubble(f"❌ **Error during execution:**\n{error_msg}", is_ai=True)
