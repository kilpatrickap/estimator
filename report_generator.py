from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from PyQt6.QtCore import QDate
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

class ReportGenerator:
    def __init__(self, estimate):
        self.estimate = estimate
        self.styles = getSampleStyleSheet()
        self._register_fonts()
        self._setup_custom_styles()

    def _register_fonts(self):
        """Registers custom fonts for Unicode support (e.g., Cedi symbol)."""
        # Try to register Arial (standard Windows font that supports most unicode)
        font_path = "C:/Windows/Fonts/arial.ttf"
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('Arial', font_path))
                self.font_name = 'Arial'
                self.bold_font_name = 'Arial' # Default to regular if bold not found
                
                # Try to find bold version too
                bold_path = "C:/Windows/Fonts/arialbd.ttf"
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont('Arial-Bold', bold_path))
                    self.bold_font_name = 'Arial-Bold'
            except Exception as e:
                print(f"Failed to register font: {e}")
                self.font_name = 'Helvetica'
                self.bold_font_name = 'Helvetica-Bold'
        else:
            self.font_name = 'Helvetica'
            self.bold_font_name = 'Helvetica-Bold'

    def _setup_custom_styles(self):
        self.styles.add(ParagraphStyle(
            name='EstimateTitle',
            parent=self.styles['Heading1'],
            fontName=self.bold_font_name,
            fontSize=24,
            textColor=colors.HexColor('#2e7d32'),
            spaceAfter=20,
            borderPadding=10,
            borderBottomWidth=2,
            borderBottomColor=colors.HexColor('#2e7d32')
        ))
        
        self.styles.add(ParagraphStyle(
            name='TaskTitle',
            parent=self.styles['Heading2'],
            fontName=self.bold_font_name,
            fontSize=14,
            textColor=colors.HexColor('#2e7d32'),
            spaceBefore=15,
            spaceAfter=10
        ))
        
        self.styles.add(ParagraphStyle(
            name='SummaryLabel',
            parent=self.styles['Normal'],
            fontName=self.font_name,
            fontSize=10,
            textColor=colors.black,
            alignment=0 # Left
        ))
        
        self.styles.add(ParagraphStyle(
            name='SummaryValue',
            parent=self.styles['Normal'],
            fontName=self.font_name,
            fontSize=10,
            textColor=colors.black,
            alignment=2 # Right
        ))

    def export_to_pdf(self, filename, company_name="", company_logo=None):
        try:
            doc = SimpleDocTemplate(
                filename,
                pagesize=A4,
                rightMargin=20*mm, leftMargin=20*mm,
                topMargin=20*mm, bottomMargin=20*mm
            )

            story = []
            symbol = self.estimate.currency.split('(')[-1].strip(')') if '(' in self.estimate.currency else '$'
            totals = self.estimate.calculate_totals()
            date_str = self.estimate.date.split()[0] if self.estimate.date else "N/A"

            # 1. Header (Logo + Company Name)
            # Prepare Logo
            logo_img = None
            if company_logo and os.path.exists(company_logo):
                from reportlab.platypus import Image
                try:
                    img = Image(company_logo)
                    # Resize: 5x smaller than original 40mm = 8mm
                    max_height = 16*mm
                    aspect = img.imageHeight / img.imageWidth
                    
                    if img.imageHeight > max_height:
                         img_height = max_height
                         img_width = max_height / aspect
                    else:
                         img_height = img.imageHeight
                         img_width = img.imageWidth
                         
                    img.drawHeight = img_height
                    img.drawWidth = img_width
                    logo_img = img
                except Exception as e:
                    print(f"Error loading logo: {e}")

            if logo_img and company_name:
                # Logo LEFT of company name
                company_para = Paragraph(company_name, self.styles['Heading3'])
                header_data = [[logo_img, company_para]]
                # Small column for logo, rest for name
                header_table = Table(header_data, colWidths=[15*mm, 155*mm])
                header_table.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('LEFTPADDING', (0,0), (-1,-1), 0),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ]))
                story.append(header_table)
            elif company_name:
                story.append(Paragraph(company_name, self.styles['Heading3']))
            elif logo_img:
                logo_img.hAlign = 'LEFT'
                story.append(logo_img)
            
            story.append(Spacer(1, 10))

            # 2. Meta Data Table
            meta_data = [
                [f"Project: {self.estimate.project_name}", f"Date: {date_str}"],
                [f"Client: {self.estimate.client_name}", f"Ref ID: #{self.estimate.id if self.estimate.id else 'New'}"]
            ]
            meta_table = Table(meta_data, colWidths=[100*mm, 70*mm])
            meta_table.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,-1), self.bold_font_name),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('TEXTCOLOR', (0,0), (-1,-1), colors.darkgray),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(meta_table)
            story.append(Spacer(1, 20))

            # 3. Tasks
            for i, task in enumerate(self.estimate.tasks, 1):
                story.append(Paragraph(f"Task {i}: {task.description}", self.styles['TaskTitle']))
                
                # Items Header
                data = [['Type', 'Description', 'Quantity', 'Rate', 'Total']]
                
                # Items Rows
                # Combine all for simplicity
                for m in task.materials:
                    data.append(['Material', m['name'], f"{m['qty']} {m['unit']}", f"{symbol}{m['unit_cost']:,.2f}", f"{symbol}{m['total']:,.2f}"])
                for l in task.labor:
                    data.append(['Labor', l['trade'], f"{l['hours']} hrs", f"{symbol}{l['rate']:,.2f}", f"{symbol}{l['total']:,.2f}"])
                for e in task.equipment:
                    data.append(['Equipment', e['name'], f"{e['hours']} hrs", f"{symbol}{e['rate']:,.2f}", f"{symbol}{e['total']:,.2f}"])
                
                if len(data) > 1:
                    # Add Subtotal Row
                    data.append(['', '', '', 'Task Subtotal:', f"{symbol}{task.get_subtotal():,.2f}"])
                    
                    t = Table(data, colWidths=[25*mm, 65*mm, 25*mm, 25*mm, 30*mm])
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
                        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                        ('ALIGN', (3,0), (-1,-1), 'RIGHT'), # Rates and Totals align right
                        ('FONTNAME', (0,0), (-1,0), self.bold_font_name), # Header bold
                        ('BOTTOMPADDING', (0,0), (-1,0), 8),
                        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f9f9f9')), # Subtotal row bg
                        ('FONTNAME', (0,-1), (-1,-1), self.bold_font_name), # Subtotal bold
                        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
                        ('FONTNAME', (1,1), (-1,-2), self.font_name), # Body rows regular
                    ]))
                    story.append(t)
                else:
                    story.append(Paragraph("No items in this task.", self.styles['Normal']))
                
                story.append(Spacer(1, 15))

            # 4. Summary Section
            story.append(Spacer(1, 10))
            story.append(Paragraph("Summary", self.styles['Heading2']))
            
            # Build Summary Data
            # Rows: Task List... Subtotal... Spacer... Add... Overhead... Profit... Spacer... Grand Total
            summary_data = []
            
            # Task break down
            for i, task in enumerate(self.estimate.tasks, 1):
                summary_data.append([f"Task {i}: {task.description}", f"{symbol}{task.get_subtotal():,.2f}"])
                
            # Subtotals line
            summary_data.append(["Sub Totals :", f"{symbol}{totals['subtotal']:,.2f}"])
            
            # Spacer
            summary_data.append(["", ""]) 
            
            # Add section
            summary_data.append(["Add :", ""])
            summary_data.append([f"Overhead ({self.estimate.overhead_percent}%):", f"{symbol}{totals['overhead']:,.2f}"])
            summary_data.append([f"Profit Margin ({self.estimate.profit_margin_percent}%):", f"{symbol}{totals['profit']:,.2f}"])
            
            # Spacer
            summary_data.append(["", ""]) 
            
            # Grand Total
            summary_data.append(["GRAND TOTAL :", f"{symbol}{totals['grand_total']:,.2f}"])

            # Create Table
            sum_table = Table(summary_data, colWidths=[80*mm, 40*mm])
            
            # Style it "Accounting" style
            style = TableStyle([
                ('ALIGN', (1,0), (1,-1), 'RIGHT'), # Right align values
                ('FONTNAME', (0,0), (-1,-1), self.font_name),
            ])
            
            # Calculate row indices
            row_idx = 0
            # Task rows are 0 to len(tasks)-1
            task_count = len(self.estimate.tasks)
            row_idx += task_count
            
            # Subtotals Row (row_idx)
            style.add('LINEABOVE', (0, row_idx), (-1, row_idx), 1, colors.black) # Border Top
            style.add('FONTNAME', (0, row_idx), (-1, row_idx), self.bold_font_name)
            row_idx += 1
            
            # Spacer (row_idx) - nothing
            row_idx += 1
            
            # Add: (row_idx)
            style.add('FONTNAME', (0, row_idx), (0, row_idx), self.bold_font_name)
            row_idx += 1
            
            # Overhead (row_idx)
            row_idx += 1
            
            # Profit (row_idx) - Border Bottom
            style.add('LINEBELOW', (0, row_idx), (-1, row_idx), 1, colors.black)
            row_idx += 1
            
            # Spacer
            row_idx += 1
            
            # Grand Total
            style.add('FONTNAME', (0, row_idx), (-1, row_idx), self.bold_font_name)
            style.add('FONTSIZE', (0, row_idx), (-1, row_idx), 14)
            style.add('TEXTCOLOR', (0, row_idx), (-1, row_idx), colors.HexColor('#2e7d32'))
            
            sum_table.setStyle(style)
            
            story.append(sum_table)

            # Build PDF
            doc.build(story)
            return True
        except Exception as e:
            print(f"PDF Generation Error: {e}")
            return False
