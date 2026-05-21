from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from PyQt6.QtCore import QDate
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
import os
import sqlite3
import json

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
                company_para = Paragraph(company_name, self.styles['Heading3'])
                header_data = [[logo_img, company_para]]
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
                [f"Client: {self.estimate.client_name}", 
                 f"Rate Code: {self.estimate.rate_code}" if getattr(self.estimate, 'rate_code', None) else f"Ref ID: #{self.estimate.id if self.estimate.id else 'New'}"]
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
                task_subtotal_base = 0

                # Generic resource iteration
                resources = [
                    ('materials', 'Material', 'name', 'qty', 'unit_cost'),
                    ('labor', 'Labor', 'trade', 'hours', 'rate'),
                    ('equipment', 'Equipment', 'name', 'hours', 'rate'),
                    ('plant', 'Plant', 'name', 'hours', 'rate'),
                    ('indirect_costs', 'Indirect', 'description', 'amount', 'amount')
                ]

                has_items = False
                for res_attr, label, name_key, qty_key, rate_key in resources:
                    items = getattr(task, res_attr)
                    for item in items:
                        has_items = True
                        # Extract currency symbol
                        curr = item.get('currency', '')
                        item_symbol = curr.split('(')[-1].strip(')') if '(' in curr else symbol
                        
                        # Format Unit
                        unit_label = item.get('unit') or ('hrs' if res_attr != 'materials' else '')
                        unit_str = f"{item[qty_key]} {unit_label}".strip()

                        data.append([
                            label, 
                            item[name_key], 
                            unit_str, 
                            f"{item_symbol}{item.get(rate_key, 0):,.2f}", # Use .get with default 0 just in case
                            f"{item_symbol}{item.get('total', 0):,.2f}"
                        ])
                        task_subtotal_base += self.estimate._get_item_total_in_base_currency(item)
                
                if has_items:
                    # Add Subtotal Row
                    data.append(['', '', '', 'Task Subtotal (Base):', f"{symbol}{task_subtotal_base:,.2f}"])
                    
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
            story.append(Paragraph("Summary (Converted to Base Currency)", self.styles['Heading2']))
            
            # Exchange Rates Used
            if self.estimate.exchange_rates:
                rates_data = [["Currency", "Exchange Rate", "Date"]]
                for curr, rdata in self.estimate.exchange_rates.items():
                    rates_data.append([curr, f"{rdata['rate']:,.4f}", rdata['date']])
                
                story.append(Paragraph("Exchange Rates Used:", self.styles['Normal']))
                rates_table = Table(rates_data, colWidths=[60*mm, 40*mm, 40*mm])
                rates_table.setStyle(TableStyle([
                    ('FONTNAME', (0,0), (-1,0), self.bold_font_name),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('FONTSIZE', (0,0), (-1,-1), 9),
                ]))
                story.append(rates_table)
                story.append(Spacer(1, 15))

            # Build Summary Data
            summary_data = []
            
            # Task break down
            for i, task in enumerate(self.estimate.tasks, 1):
                task_total = 0
                for item in task.all_items:
                    task_total += self.estimate._get_item_total_in_base_currency(item)
                summary_data.append([f"Task {i}: {task.description}", f"{symbol}{task_total:,.2f}"])
                
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


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, num_pages):
        self.saveState()
        
        # Page 1 (Cover Page) doesn't get headers or footers
        if self._pageNumber == 1:
            self.restoreState()
            return
            
        font = "Arial" if "Arial" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
        
        # 1. Header
        self.setFont(font, 8)
        self.setFillColor(colors.HexColor('#64748b'))
        self.drawString(56, 800, "EXECUTIVE PROJECT INTELLIGENCE REPORT")
        
        # Header Line
        self.setStrokeColor(colors.HexColor('#cbd5e1'))
        self.setLineWidth(0.5)
        self.line(56, 792, 538, 792)
        
        # 2. Footer
        footer_text = f"Page {self._pageNumber} of {num_pages}"
        self.drawRightString(538, 30, footer_text)
        self.drawString(56, 30, "CONFIDENTIAL - PREPARED FOR EXECUTIVE REVIEW")
        
        # Footer Line
        self.setStrokeColor(colors.HexColor('#cbd5e1'))
        self.setLineWidth(0.5)
        self.line(56, 42, 538, 42)
        
        self.restoreState()


class ExecutiveAnalyticsReportGenerator:
    def __init__(self, project_dir):
        self.project_dir = os.path.abspath(project_dir)
        self.pboq_folder = os.path.join(self.project_dir, "Priced BOQs")
        self.pj_db_dir = os.path.join(self.project_dir, "Project Database")
        self.pboq_state_dir = os.path.join(self.project_dir, "PBOQ States")
        
        # Initialize styles
        self.styles = getSampleStyleSheet()
        self._register_fonts()
        self._setup_custom_styles()
        self._rate_cache = {}

    def _register_fonts(self):
        font_path = "C:/Windows/Fonts/arial.ttf"
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('Arial', font_path))
                self.font_name = 'Arial'
                self.bold_font_name = 'Arial'
                
                bold_path = "C:/Windows/Fonts/arialbd.ttf"
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont('Arial-Bold', bold_path))
                    self.bold_font_name = 'Arial-Bold'
            except Exception as e:
                print(f"Failed to register font in executive report: {e}")
                self.font_name = 'Helvetica'
                self.bold_font_name = 'Helvetica-Bold'
        else:
            self.font_name = 'Helvetica'
            self.bold_font_name = 'Helvetica-Bold'

    def _setup_custom_styles(self):
        # Custom style for title & headers
        self.styles.add(ParagraphStyle(
            name='ExecTitle',
            parent=self.styles['Heading1'],
            fontName=self.bold_font_name,
            fontSize=22,
            textColor=colors.HexColor('#1b5e20'),
            spaceAfter=15,
            alignment=1 # Centered
        ))
        self.styles.add(ParagraphStyle(
            name='ExecSubtitle',
            parent=self.styles['Normal'],
            fontName=self.font_name,
            fontSize=12,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=25,
            alignment=1
        ))
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontName=self.bold_font_name,
            fontSize=14,
            textColor=colors.HexColor('#1b5e20'),
            spaceBefore=15,
            spaceAfter=8,
            borderPadding=4,
            borderBottomWidth=1,
            borderBottomColor=colors.HexColor('#cbd5e1')
        ))
        self.styles.add(ParagraphStyle(
            name='BodyDesc',
            parent=self.styles['Normal'],
            fontName=self.font_name,
            fontSize=9.5,
            textColor=colors.HexColor('#334155'),
            spaceAfter=12
        ))
        self.styles.add(ParagraphStyle(
            name='CoverMetaLabel',
            parent=self.styles['Normal'],
            fontName=self.bold_font_name,
            fontSize=10,
            textColor=colors.HexColor('#475569')
        ))
        self.styles.add(ParagraphStyle(
            name='CoverMetaVal',
            parent=self.styles['Normal'],
            fontName=self.font_name,
            fontSize=10,
            textColor=colors.HexColor('#0f172a')
        ))
        self.styles.add(ParagraphStyle(
            name='KpiCardText',
            parent=self.styles['Normal'],
            fontName=self.font_name,
            fontSize=9,
            textColor=colors.HexColor('#334155'),
            alignment=1
        ))
        self.styles.add(ParagraphStyle(
            name='TableHeaderStyle',
            parent=self.styles['Normal'],
            fontName=self.bold_font_name,
            fontSize=9,
            textColor=colors.HexColor('#64748b'),
            alignment=0
        ))
        self.styles.add(ParagraphStyle(
            name='TableBodyStyle',
            parent=self.styles['Normal'],
            fontName=self.font_name,
            fontSize=8.5,
            textColor=colors.HexColor('#1e293b'),
            alignment=0
        ))
        self.styles.add(ParagraphStyle(
            name='TableBodyStyleRight',
            parent=self.styles['Normal'],
            fontName=self.font_name,
            fontSize=8.5,
            textColor=colors.HexColor('#1e293b'),
            alignment=2 # Right
        ))
        self.styles.add(ParagraphStyle(
            name='TableBodyStyleBoldRight',
            parent=self.styles['Normal'],
            fontName=self.bold_font_name,
            fontSize=8.5,
            textColor=colors.HexColor('#1e293b'),
            alignment=2
        ))
        self.styles.add(ParagraphStyle(
            name='TableBodyStyleBold',
            parent=self.styles['Normal'],
            fontName=self.bold_font_name,
            fontSize=8.5,
            textColor=colors.HexColor('#1e293b'),
            alignment=0
        ))

    def _to_float(self, val):
        if not val: return 0.0
        try: return float(str(val).replace(',', '').replace(' ', '').replace('₵','').replace('$','').strip())
        except: return 0.0

    def _get_net_rate(self, rate_code, cursor):
        if not rate_code: return 0.0
        if rate_code in self._rate_cache: return self._rate_cache[rate_code]
        try:
            cursor.execute("SELECT net_total FROM estimates WHERE rate_code = ?", (rate_code,))
            res = cursor.fetchone()
            if res:
                net = float(res[0] or 0.0)
                self._rate_cache[rate_code] = net
                return net
        except: pass
        self._rate_cache[rate_code] = 0.0
        return 0.0

    def _get_rate_composition(self, rate_code):
        """Analyzes a rate buildup and returns (ratios, unit_net_total, category)."""
        if not rate_code: return None, 0.0, None
        if rate_code in self._rate_cache and isinstance(self._rate_cache[rate_code], tuple):
            return self._rate_cache[rate_code]

        try:
            dbs = [f for f in os.listdir(self.pj_db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
            if not dbs: return None, 0.0, None
            
            db_path = os.path.join(self.pj_db_dir, dbs[0])
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if category column exists in estimates table
            cursor.execute("PRAGMA table_info(estimates)")
            cols = [col[1] for col in cursor.fetchall()]
            has_category = "category" in cols

            # Find the estimate ID, Net Total, and Category for this rate code
            if has_category:
                cursor.execute("SELECT id, net_total, category FROM estimates WHERE rate_code = ?", (rate_code,))
                res = cursor.fetchone()
                if not res: 
                    conn.close()
                    return None, 0.0, None
                est_id, net_total, category = res
            else:
                cursor.execute("SELECT id, net_total FROM estimates WHERE rate_code = ?", (rate_code,))
                res = cursor.fetchone()
                if not res: 
                    conn.close()
                    return None, 0.0, None
                est_id, net_total = res
                category = "Uncategorized"
            net_total = float(net_total or 0.0)
            
            comp = {'Materials': 0.0, 'Labor': 0.0, 'Equipment': 0.0, 'Plant': 0.0, 'Indirect': 0.0, 'Subcontractors': 0.0}
            
            # Query all associated resources
            try:
                cursor.execute("""
                    SELECT SUM(price * quantity) FROM estimate_materials 
                    WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
                """, (est_id,))
                comp['Materials'] = cursor.fetchone()[0] or 0.0
            except: pass
            
            try:
                cursor.execute("""
                    SELECT SUM(rate * hours) FROM estimate_labor 
                    WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
                """, (est_id,))
                comp['Labor'] = cursor.fetchone()[0] or 0.0
            except: pass
            
            try:
                cursor.execute("""
                    SELECT SUM(rate * hours) FROM estimate_equipment 
                    WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
                """, (est_id,))
                comp['Equipment'] = cursor.fetchone()[0] or 0.0
            except: pass
            
            try:
                cursor.execute("""
                    SELECT SUM(rate * hours) FROM estimate_plant 
                    WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
                """, (est_id,))
                comp['Plant'] = cursor.fetchone()[0] or 0.0
            except: pass
            
            try:
                cursor.execute("""
                    SELECT SUM(amount) FROM estimate_indirect_costs 
                    WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
                """, (est_id,))
                comp['Indirect'] = cursor.fetchone()[0] or 0.0
            except: pass
            
            # Subcontractors in buildup (Join with quotes to get rates)
            try:
                cursor.execute("""
                    SELECT SUM(esr.quantity * sq.rate) 
                    FROM estimate_sub_rates esr
                    JOIN subcontractor_quotes sq ON esr.sub_rate_id = sq.id
                    WHERE esr.estimate_id = ?
                """, (est_id,))
                comp['Subcontractors'] = cursor.fetchone()[0] or 0.0
            except: pass
            
            total = sum(comp.values())
            ratios = None
            if total > 0:
                ratios = {k: v / total for k, v in comp.items()}
            
            val = (ratios, net_total, category)
            self._rate_cache[rate_code] = val
            conn.close()
            return ratios, net_total, category
        except Exception as e:
            print("Error retrieving rate composition:", e)
        return None, 0.0, None

    def _get_subcontractor_target_rates(self, desc, subbee_code):
        """
        Retrieves the original target rates (PlugRate, SubbeeRate) for a subcontractor item
        from the Master database pboq_items table.
        """
        target_plug_rate = 0.0
        target_subbee_rate = 0.0
        
        # Determine the master database file path
        if not hasattr(self, 'master_db_path'):
            self.master_db_path = None
            if os.path.exists(self.pj_db_dir):
                dbs = [f for f in os.listdir(self.pj_db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
                if dbs:
                    self.master_db_path = os.path.join(self.pj_db_dir, dbs[0])
                    
        if not self.master_db_path:
            return None
            
        try:
            conn = sqlite3.connect(self.master_db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(pboq_items)")
            cols = [info[1] for info in cursor.fetchall()]
            
            p_col = next((c for c in cols if c.lower() in ["plugrate", "plug_rate"]), None)
            s_col = next((c for c in cols if c.lower() in ["subbeerate", "sub_rate"]), None)
            c_col = next((c for c in cols if c.lower() in ["subbeecode", "sub_code"]), None)
            d_col = next((c for c in cols if c.lower() in ["description", "desc"]), None)
            
            if not p_col or not s_col or not c_col or not d_col:
                conn.close()
                return None
                
            code_target = None
            if subbee_code and len(subbee_code) > 0:
                code_target = subbee_code[:-1] + 'A'
                
            # 1. Try with code target
            if code_target:
                cursor.execute(f"SELECT \"{p_col}\", \"{s_col}\" FROM pboq_items WHERE \"{c_col}\" = ?", (code_target,))
                res = cursor.fetchone()
                if res:
                    target_plug_rate, target_subbee_rate = float(res[0] or 0.0), float(res[1] or 0.0)
                    conn.close()
                    return target_plug_rate, target_subbee_rate
                    
            # 2. Try with description and code ends with 'A'
            cursor.execute(f"SELECT \"{p_col}\", \"{s_col}\" FROM pboq_items WHERE \"{d_col}\" = ? AND \"{c_col}\" LIKE '%A'", (desc,))
            res = cursor.fetchone()
            if res:
                target_plug_rate, target_subbee_rate = float(res[0] or 0.0), float(res[1] or 0.0)
                conn.close()
                return target_plug_rate, target_subbee_rate
                
            # 3. Try with description only
            cursor.execute(f"SELECT \"{p_col}\", \"{s_col}\" FROM pboq_items WHERE \"{d_col}\" = ?", (desc,))
            res = cursor.fetchone()
            if res:
                target_plug_rate, target_subbee_rate = float(res[0] or 0.0), float(res[1] or 0.0)
                conn.close()
                return target_plug_rate, target_subbee_rate
                
            conn.close()
        except Exception as e:
            print("Error retrieving target subcontractor rates:", e)
            
        return None

    def _get_pboq_mapping(self, filename):
        state_path = os.path.join(self.pboq_state_dir, filename + ".json")
        if os.path.exists(state_path):
            try:
                with open(state_path, 'r') as f:
                    data = json.load(f)
                    return data.get('mappings', {})
            except: pass
        return {}

    def _get_project_meta(self):
        project_name = os.path.basename(self.project_dir)
        client_name = "Internal Board"
        currency_symbol = "$"
        overhead_rate = 0.0
        profit_rate = 0.0
        
        try:
            if os.path.exists(self.pj_db_dir):
                dbs = [f for f in os.listdir(self.pj_db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
                if dbs:
                    db_path = os.path.join(self.pj_db_dir, dbs[0])
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    
                    # 1. Project Name / Client Name
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimates'")
                    if cursor.fetchone():
                        cursor.execute("SELECT project_name, client_name, currency FROM estimates LIMIT 1")
                        res = cursor.fetchone()
                        if res:
                            if res[0]: project_name = res[0]
                            if res[1]: client_name = res[1]
                            if res[2] and '(' in res[2]:
                                currency_symbol = res[2].split('(')[-1].strip(')')
                            elif res[2]:
                                currency_symbol = res[2]
                                
                    # 2. Overheads / Profit
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
                    if cursor.fetchone():
                        cursor.execute("SELECT value FROM settings WHERE key='overhead'")
                        row = cursor.fetchone()
                        if row: overhead_rate = self._to_float(row[0])
                        
                        cursor.execute("SELECT value FROM settings WHERE key='profit'")
                        row = cursor.fetchone()
                        if row: profit_rate = self._to_float(row[0])
                        
                    conn.close()
        except Exception as e:
            print(f"Error gathering metadata: {e}")
            
        return {
            'project_name': project_name,
            'client_name': client_name,
            'currency_symbol': currency_symbol,
            'overhead_rate': overhead_rate,
            'profit_rate': profit_rate
        }

    def _gather_analytics_data(self, meta):
        # 1. Initialize stats containers
        total_items = 0
        priced_items = 0
        flagged_items = 0
        total_net_cost = 0.0
        
        sources_net = {
            'gross': 0.0, 
            'plug': 0.0, 
            'sub': 0.0, 
            'provisional': 0.0,
            'pc_sum': 0.0,
            'daywork': 0.0
        }
        
        sheet_net = {}
        sheet_stats = {}
        all_items_flat = []
        
        # Operational BOM and subcontractor trackers
        all_materials = {}
        all_labor = {}
        sub_alloc = 0.0
        all_packages_commit = {} # (package, subcontractor) -> value
        rate_codes_tracker = []
        
        # 2. Scan Priced BOQs
        if os.path.exists(self.pboq_folder):
            db_files = [f for f in os.listdir(self.pboq_folder) if f.lower().endswith('.db')]
            
            for f in db_files:
                db_path = os.path.join(self.pboq_folder, f)
                mapping = self._get_pboq_mapping(f)
                
                qty_col_idx = mapping.get('qty', -1)
                desc_col_idx = mapping.get('desc', -1)
                bill_rate_col_idx = mapping.get('bill_rate', -1)
                bill_amt_col_idx = mapping.get('bill_amount', -1)
                
                # Fetch dummy rate from state file if available
                dummy_val = 0.1
                state_file_path = os.path.join(self.pboq_state_dir, f + ".json")
                if os.path.exists(state_file_path):
                    try:
                        with open(state_file_path, 'r') as sf:
                            sdata = json.load(sf)
                            dummy_val = sdata.get('dummy_rate', 0.1)
                    except: pass
                
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(pboq_items)")
                    cols = [info[1] for info in cursor.fetchall()]
                    
                    qty_name = cols[qty_col_idx + 1] if qty_col_idx >= 0 and (qty_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["quantity", "qty"]), None)
                    desc_name = cols[desc_col_idx + 1] if desc_col_idx >= 0 and (desc_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["description", "desc"]), None)
                    bill_rate_name = cols[bill_rate_col_idx + 1] if bill_rate_col_idx >= 0 and (bill_rate_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["bill rate", "billrate"]), None)
                    bill_amt_name = cols[bill_amt_col_idx + 1] if bill_amt_col_idx >= 0 and (bill_amt_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["bill amount", "billamount"]), None)
                    
                    col_map = {
                        'sheet': next((c for c in cols if c.lower() == 'sheet'), None),
                        'desc': desc_name,
                        'qty': qty_name,
                        'bill_rate': bill_rate_name,
                        'bill_amt': bill_amt_name,
                        'gross': next((c for c in cols if c.lower() in ["grossrate", "gross_rate"]), None),
                        'plug': next((c for c in cols if c.lower() in ["plugrate", "plug_rate"]), None),
                        'sub': next((c for c in cols if c.lower() in ["subbeerate", "sub_rate"]), None),
                        'prov': next((c for c in cols if c.lower() in ["provsum", "prov_sum"]), None),
                        'pc': next((c for c in cols if c.lower() in ["pcsum", "pc_sum"]), None),
                        'dw': next((c for c in cols if c.lower() in ["daywork"]), None),
                        'flag': next((c for c in cols if c.lower() == "isflagged"), None),
                        'rcode': next((c for c in cols if c.lower() in ["ratecode", "rate_code"]), None),
                        'pcode': next((c for c in cols if c.lower() in ["plugcode", "plug_code"]), None),
                        'spkg': next((c for c in cols if c.lower() in ["sub_package", "subpackage", "subbeepackage"]), None),
                        'sname': next((c for c in cols if c.lower() in ["sub_name", "subname", "subbeename"]), None),
                        'sub_code': next((c for c in cols if c.lower() in ["subbeecode", "sub_code"]), None)
                    }
                    
                    if not (col_map['desc'] and col_map['qty']):
                        conn.close()
                        continue
                        
                    query_cols = []
                    for k in ['sheet', 'desc', 'qty', 'bill_rate', 'bill_amt', 'gross', 'plug', 'sub', 'prov', 'pc', 'dw', 'flag', 'rcode', 'pcode', 'spkg', 'sname', 'sub_code']:
                        if col_map[k]: query_cols.append(f"\"{col_map[k]}\"")
                        else: query_cols.append("''")
                        
                    cursor.execute(f"SELECT {', '.join(query_cols)} FROM pboq_items")
                    rows = cursor.fetchall()
                    
                    # Also need to get project estimates net cache
                    pj_db_cursor = None
                    pj_db_conn = None
                    try:
                        pj_dbs = [x for x in os.listdir(self.pj_db_dir) if x.lower().endswith('.db') and 'rates' not in x.lower()]
                        if pj_dbs:
                            pj_db_conn = sqlite3.connect(os.path.join(self.pj_db_dir, pj_dbs[0]))
                            pj_db_cursor = pj_db_conn.cursor()
                    except: pass
                    
                    for r in rows:
                        sheet, desc, q, br, ba, gross, plug, sub, prov, pc, dw, flag, rcode, pcode, spkg, sname, sub_code = r
                        desc_low = (desc or "").lower()
                        if not str(desc).strip() or "collection" in desc_low or "summary" in desc_low:
                            continue
                            
                        qty_f = self._to_float(q)
                        bill_rate_f = self._to_float(br)
                        bill_amt_f = self._to_float(ba)
                        
                        if qty_f == 0 and bill_amt_f == 0:
                            continue
                        
                        g_val = self._to_float(gross)
                        p_val = self._to_float(plug)
                        s_val = self._to_float(sub)
                        pr_val = self._to_float(prov)
                        pc_val = self._to_float(pc)
                        d_val = self._to_float(dw)
                        
                        is_row_priced = (g_val > 0 or p_val > 0 or s_val > 0 or pr_val > 0 or pc_val > 0 or d_val > 0)
                        if not is_row_priced:
                            if bill_rate_f > 0 and abs(bill_rate_f - dummy_val) > 0.0001:
                                is_row_priced = True
                                
                        is_priced = is_row_priced
                        
                        active_code = pcode if pcode and str(pcode).strip() else rcode
                        ratios, master_net_cost, master_cat = self._get_rate_composition(active_code) if active_code else (None, 0.0, None)
                        
                        sub_ratio = 0.0
                        if ratios:
                            sub_ratio = ratios.get('Subcontractors', 0.0)
                        elif s_val > 0:
                            sub_ratio = 1.0
                            
                        unit_cost = 0.0
                        src = None
                        
                        if pr_val > 0: unit_cost = pr_val; src = 'provisional'
                        elif pc_val > 0: unit_cost = pc_val; src = 'pc_sum'
                        elif d_val > 0: unit_cost = d_val; src = 'daywork'
                        elif master_net_cost > 0: unit_cost = master_net_cost; src = 'gross'
                        else:
                            if p_val > 0: unit_cost = p_val; src = 'plug'
                            elif s_val > 0: unit_cost = s_val; src = 'sub'
                            elif g_val > 0: unit_cost = g_val; src = 'gross'
                            else:
                                if bill_amt_f > 0:
                                    unit_cost = bill_amt_f if qty_f <= 1 else 0.0
                                    src = 'gross'
                                
                        calc_qty = qty_f if qty_f > 0 else (1.0 if bill_amt_f > 0 else 0.0)
                        item_cost = unit_cost * calc_qty if is_priced else 0.0
                        
                        # Calculate original/target subcontractor values if applicable
                        sub_bid = bill_amt_f
                        sub_cost = item_cost
                        if sub_ratio > 0:
                            target_rates = self._get_subcontractor_target_rates(desc, sub_code)
                            if target_rates:
                                target_plug_rate, target_subbee_rate = target_rates
                                sub_bid = target_plug_rate * calc_qty
                                sub_cost = target_subbee_rate * calc_qty
                                
                        eff_bid = (sub_bid * sub_ratio) + (bill_amt_f * (1.0 - sub_ratio))
                        eff_cost = (sub_cost * sub_ratio) + (item_cost * (1.0 - sub_ratio))
                        
                        item_net_cost = round(eff_cost, 2) if is_priced else 0.0
                        
                        total_items += 1
                        if is_priced: priced_items += 1
                        total_net_cost += item_net_cost
                        
                        if is_priced:
                            sub_portion = sub_cost * sub_ratio
                            non_sub_portion = item_cost * (1.0 - sub_ratio)
                            sources_net['sub'] += sub_portion
                            if src:
                                sources_net[src] += non_sub_portion
                            
                        # Save in Pareto all items tracker
                        if is_priced and item_net_cost > 0:
                            all_items_flat.append({
                                'desc': desc,
                                'qty': calc_qty,
                                'unit_cost': unit_cost,
                                'total_cost': eff_cost,
                                'total_bid': eff_bid,
                                'sheet': f"{f.replace('.db', '')} - {sheet}",
                                'rcode': active_code or "",
                                'flagged': bool(flag and str(flag) == '1')
                            })
                            
                        if flag and str(flag) == '1':
                            flagged_items += 1
                            
                        sheet_key = f"{f.replace('.db', '')} - {sheet}"
                        if sheet_key not in sheet_net:
                            sheet_net[sheet_key] = 0.0
                            sheet_stats[sheet_key] = {'total': 0, 'priced': 0}
                            
                        sheet_net[sheet_key] += item_net_cost
                        sheet_stats[sheet_key]['total'] += 1
                        if is_priced: sheet_stats[sheet_key]['priced'] += 1
                        
                        # Operational Logistics support
                        if is_priced:
                            if s_val > 0:
                                rate_codes_tracker.append({
                                    'r_code': "",
                                    'qty': calc_qty,
                                    'sub_rate': s_val,
                                    'package': str(spkg or "Uncategorized").strip(),
                                    'subbee': str(sname or "Open").strip()
                                })
                            elif active_code:
                                rate_codes_tracker.append({
                                    'r_code': str(active_code).strip(),
                                    'qty': calc_qty,
                                    'sub_rate': 0.0,
                                    'package': str(spkg or "Uncategorized").strip(),
                                    'subbee': str(sname or "Open").strip()
                                })
                                
                    conn.close()
                    if pj_db_conn: pj_db_conn.close()
                except Exception as e:
                    print(f"Error gathering analytics from {f}: {e}")
                    
        # Apply markups to sources, net and sheets
        combined_markup_pct = (meta['overhead_rate'] + meta['profit_rate']) / 100.0
        total_bid_value = total_net_cost * (1.0 + combined_markup_pct)
        sources_bid = {k: v * (1.0 + combined_markup_pct) for k, v in sources_net.items()}
        
        sheet_data_bid = []
        for k, net_val in sheet_net.items():
            sheet_data_bid.append({
                'name': k,
                'amount': net_val * (1.0 + combined_markup_pct),
                'total': sheet_stats[k]['total'],
                'priced': sheet_stats[k]['priced']
            })
        # Sort sheets by value descending
        sheet_data_bid = sorted(sheet_data_bid, key=lambda x: x['amount'], reverse=True)

        # 3. Pull materials and labor details from project database for BOM
        try:
            pj_dbs = [f for f in os.listdir(self.pj_db_dir) if f.lower().endswith('.db') and 'rates' not in f.lower()]
            if pj_dbs:
                db_path = os.path.join(self.pj_db_dir, pj_dbs[0])
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                for item in rate_codes_tracker:
                    r_code = item['r_code']
                    boq_qty = item['qty']
                    s_rate = item['sub_rate']
                    pkg_name = item['package']
                    sub_name = item['subbee']
                    
                    if s_rate > 0:
                        amt = s_rate * boq_qty
                        sub_alloc += amt
                        
                        key = (pkg_name, sub_name)
                        if key not in all_packages_commit: all_packages_commit[key] = 0.0
                        all_packages_commit[key] += amt
                        continue
                        
                    if not r_code or r_code == 'Sheet': continue
                    
                    cursor.execute("SELECT id FROM estimates WHERE rate_code = ?", (r_code,))
                    res = cursor.fetchone()
                    if not res: continue
                    est_id = res[0]
                    
                    # Material aggregates
                    cursor.execute("""
                        SELECT name, unit, quantity, price FROM estimate_materials 
                        WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
                    """, (est_id,))
                    for m_name, m_unit, m_qty, m_price in cursor.fetchall():
                        m_total_qty = (m_qty or 0) * boq_qty
                        m_total_cost = m_total_qty * (m_price or 0)
                        
                        key = f"{m_name} ({m_unit})"
                        if key not in all_materials:
                            all_materials[key] = {'name': m_name, 'unit': m_unit, 'qty': 0.0, 'cost': 0.0}
                        all_materials[key]['qty'] += m_total_qty
                        all_materials[key]['cost'] += m_total_cost

                    # Labor aggregates
                    cursor.execute("""
                        SELECT name_trade, unit, hours, rate FROM estimate_labor 
                        WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
                    """, (est_id,))
                    for l_name, l_unit, l_hours, l_rate in cursor.fetchall():
                        l_total_hours = (l_hours or 0) * boq_qty
                        l_total_cost = l_total_hours * (l_rate or 0)
                        
                        key = f"{l_name} ({l_unit})"
                        if key not in all_labor:
                            all_labor[key] = {'name': l_name, 'unit': l_unit, 'qty': 0.0, 'cost': 0.0}
                        all_labor[key]['qty'] += l_total_hours
                        all_labor[key]['cost'] += l_total_cost
                        
                conn.close()
        except Exception as e:
            print(f"Error reading DB in executive report logistics scan: {e}")

        # Material total / Labor total
        mat_total = sum(v['cost'] for v in all_materials.values())
        lab_total = sum(v['cost'] for v in all_labor.values())
        
        # 4. Pull supply chain packages and bids for Adjudication list
        all_adjudication_packages = []
        try:
            if os.path.exists(self.pboq_folder):
                db_files = [f for f in os.listdir(self.pboq_folder) if f.lower().endswith('.db')]
                for f in db_files:
                    db_path = os.path.join(self.pboq_folder, f)
                    mapping = self._get_pboq_mapping(f)
                    
                    q_idx = mapping.get('qty')
                    br_idx = mapping.get('bill_rate')
                    pkg_idx = mapping.get('sub_package')
                    sw_idx = mapping.get('sub_name')
                    sr_idx = mapping.get('sub_rate')
                    
                    if q_idx is None or br_idx is None or pkg_idx is None: continue
                    
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(pboq_items)")
                    cols = [info[1] for info in cursor.fetchall()]
                    
                    q_col = cols[q_idx + 1]
                    br_col = cols[br_idx + 1]
                    pkg_col = cols[pkg_idx + 1]
                    sw_col = cols[sw_idx + 1] if sw_idx is not None else None
                    sr_col = cols[sr_idx + 1] if sr_idx is not None else None
                    
                    d_col = next((c for c in cols if c.lower() in ["description", "desc"]), None)
                    sub_code_col = next((c for c in cols if c.lower() in ["subbeecode", "sub_code"]), None)
                    
                    sel_cols = [f'"{pkg_col}"', f'"{q_col}"', f'"{br_col}"', "rowid"]
                    if sw_col: sel_cols.append(f'"{sw_col}"')
                    if sr_col: sel_cols.append(f'"{sr_col}"')
                    if d_col: sel_cols.append(f'"{d_col}"')
                    else: sel_cols.append("''")
                    if sub_code_col: sel_cols.append(f'"{sub_code_col}"')
                    else: sel_cols.append("''")
                    
                    query = f"SELECT {', '.join(sel_cols)} FROM pboq_items WHERE \"{pkg_col}\" IS NOT NULL AND \"{pkg_col}\" != ''"
                    cursor.execute(query)
                    
                    pkg_items = {}
                    pkg_data = {} # name -> {target, winner_name, winner_val}
                    for row in cursor.fetchall():
                        p_name = row[0]
                        qty = self._to_float(row[1])
                        target = self._to_float(row[2])
                        rid = row[3]
                        w_name = row[4] if len(row) > 4 else ""
                        w_val = self._to_float(row[5]) if len(row) > 5 else 0.0
                        desc = row[6] if len(row) > 6 else ""
                        sub_code = row[7] if len(row) > 7 else ""
                        
                        target_rates = self._get_subcontractor_target_rates(desc, sub_code)
                        if target_rates:
                            target_plug_rate, target_subbee_rate = target_rates
                            if target_plug_rate > 0:
                                target = target_plug_rate
                                
                        if p_name not in pkg_data:
                            pkg_data[p_name] = {'target': 0.0, 'winner_name': "", 'winner_val': 0.0, 'bids': {}}
                        
                        pkg_data[p_name]['target'] += (qty * target)
                        pkg_data[p_name]['winner_val'] += (qty * w_val)
                        if w_name and not pkg_data[p_name]['winner_name']:
                            pkg_data[p_name]['winner_name'] = w_name
                            
                        if p_name not in pkg_items: pkg_items[p_name] = {}
                        pkg_items[p_name][rid] = {'qty': qty, 'target': target}
                        
                    # Get bids
                    cursor.execute("SELECT package_name, subcontractor_name, row_idx, rate FROM subcontractor_quotes")
                    for p_name, s_name, rid, rate in cursor.fetchall():
                        if p_name in pkg_data and rid in pkg_items[p_name]:
                            qty = pkg_items[p_name][rid]['qty']
                            amt = qty * (rate or 0)
                            if s_name not in pkg_data[p_name]['bids']:
                                pkg_data[p_name]['bids'][s_name] = 0.0
                            pkg_data[p_name]['bids'][s_name] += amt
                            
                    for name, d in pkg_data.items():
                        all_adjudication_packages.append({
                            'package_name': name,
                            'target_val': d['target'],
                            'winner_name': d['winner_name'] or "Open",
                            'winner_val': d['winner_val'],
                            'quotes': d['bids']
                        })
                    conn.close()
        except Exception as e:
            print(f"Error scanning supply chain: {e}")

        # 5. Parametric Benchmarking Cost Modelling State
        benchmark_data = {
            'gfa': 150.0,
            'b_type': 'Residential House',
            'region': 'Accra',
            'spec': 'Standard / Medium Quality',
            'complexity': 'Moderate (1.15x)',
            'site': 'Standard Flat Ground',
            'wet_areas': 2,
            'simulated_rate': 0.0,
            'simulated_total': 0.0,
            'actual_rate': 0.0
        }
        try:
            state_file = os.path.join(self.pboq_state_dir, "parametric_state.json")
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    benchmark_data['gfa'] = float(state.get('gfa', 150.0))
                    
                    types = ["Residential House", "Commercial Office", "Retail / Showroom", "Industrial / Warehouse", "Extension / Add-on"]
                    building_type_idx = state.get('building_type_idx', 0)
                    benchmark_data['b_type'] = types[building_type_idx] if building_type_idx < len(types) else "Residential House"
                    
                    regions = ["Accra Baseline", "Kumasi Region", "Takoradi Area", "Tamale District", "Other Locations"]
                    region_idx = state.get('region_idx', 0)
                    benchmark_data['region'] = regions[region_idx] if region_idx < len(regions) else "Accra Baseline"
                    
                    specs = ["Economy / Low Spec", "Standard / Medium Quality", "High-End Quality Finishes", "Premium Luxury Finishes"]
                    spec_idx = state.get('spec_idx', 0)
                    benchmark_data['spec'] = specs[spec_idx] if spec_idx < len(specs) else "Standard / Medium Quality"
                    
                    complexities = ["Simple (1.00x)", "Moderate (1.15x)", "High (1.35x)"]
                    complexity_idx = state.get('complexity_idx', 0)
                    benchmark_data['complexity'] = complexities[complexity_idx] if complexity_idx < len(complexities) else "Moderate (1.15x)"
                    
                    sites = ["Standard Flat Ground", "Sloped Ground (1.12x)", "Difficult Ground (1.25x)"]
                    site_idx = state.get('site_conditions_idx', 0)
                    benchmark_data['site'] = sites[site_idx] if site_idx < len(sites) else "Standard Flat Ground"
                    
                    benchmark_data['wet_areas'] = int(state.get('wet_areas', 2))
                    
                    # Run cost calculations matching cost modelling
                    base_rates = {
                        "Residential House": 750.0,
                        "Commercial Office": 1200.0,
                        "Retail / Showroom": 950.0,
                        "Industrial / Warehouse": 500.0,
                        "Extension / Add-on": 800.0
                    }
                    base_rate = base_rates.get(benchmark_data['b_type'], 750.0)
                    
                    region_factors = [1.0, 0.90, 0.95, 0.85, 0.80]
                    region_factor = region_factors[region_idx] if region_idx < len(region_factors) else 1.0
                    
                    spec_multipliers = [1.0, 1.30, 1.80, 2.50]
                    spec_mult = spec_multipliers[spec_idx] if spec_idx < len(spec_multipliers) else 1.30
                    
                    comp_multipliers = [1.0, 1.15, 1.35]
                    comp_mult = comp_multipliers[complexity_idx] if complexity_idx < len(comp_multipliers) else 1.15
                    
                    site_multipliers = [1.0, 1.12, 1.25]
                    site_mult = site_multipliers[site_idx] if site_idx < len(site_multipliers) else 1.0
                    
                    wet_premiums = [8000.0, 12000.0, 20000.0, 35000.0]
                    wet_prem_rate = wet_premiums[spec_idx] if spec_idx < len(wet_premiums) else 12000.0
                    total_wet_cost = benchmark_data['wet_areas'] * wet_prem_rate
                    
                    dr_base = base_rate * region_factor
                    dr_spec = dr_base * (spec_mult - 1.0)
                    dr_comp = (dr_base * spec_mult) * (comp_mult - 1.0)
                    dr_site = (dr_base * spec_mult * comp_mult) * (site_mult - 1.0)
                    dr_wet = total_wet_cost / benchmark_data['gfa'] if benchmark_data['gfa'] > 0 else 0.0
                    
                    simulated_rate = dr_base + dr_spec + dr_comp + dr_site + dr_wet
                    benchmark_data['simulated_rate'] = simulated_rate
                    benchmark_data['simulated_total'] = simulated_rate * benchmark_data['gfa']
                    
            if total_net_cost > 0 and benchmark_data['gfa'] > 0:
                benchmark_data['actual_rate'] = total_bid_value / benchmark_data['gfa']
        except Exception as e:
            print(f"Error computing Cost Modelling benchmark: {e}")

        # 6. Build and Return results packages
        return {
            'total_items': total_items,
            'priced_items': priced_items,
            'flagged_items': flagged_items,
            'total_net_cost': total_net_cost,
            'total_bid_value': total_bid_value,
            'sources': sources_bid,
            'sheet_breakdown': sheet_data_bid,
            'all_items_flat': all_items_flat,
            'materials': all_materials,
            'labor': all_labor,
            'sub_alloc': sub_alloc,
            'packages_commit': all_packages_commit,
            'adjudication': all_adjudication_packages,
            'benchmark': benchmark_data
        }

    def generate_report(self, filename):
        try:
            # 1. Meta and Analytics
            meta = self._get_project_meta()
            data = self._gather_analytics_data(meta)
            
            # Margins: 56.69pt = 20mm
            doc = SimpleDocTemplate(
                filename,
                pagesize=A4,
                leftMargin=56, rightMargin=56,
                topMargin=56, bottomMargin=56
            )
            
            story = []
            symbol = meta['currency_symbol'].strip()
            
            # --- PAGE 1: COVER PAGE ---
            story.append(Spacer(1, 120))
            story.append(Paragraph("EXECUTIVE PROJECT INTELLIGENCE REPORT", self.styles['ExecTitle']))
            story.append(Paragraph("Comprehensive Portfolio Analytics & Financial Audit", self.styles['ExecSubtitle']))
            
            # Horizontal Divider
            dec_table = Table([[""]], colWidths=[483], rowHeights=[4])
            dec_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#1b5e20')),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 0),
            ]))
            story.append(dec_table)
            story.append(Spacer(1, 40))
            
            # Metadata Box
            meta_rows = [
                [Paragraph("<b>Project Folder</b>", self.styles['CoverMetaLabel']), Paragraph(os.path.basename(self.project_dir), self.styles['CoverMetaVal'])],
                [Paragraph("<b>Project Name</b>", self.styles['CoverMetaLabel']), Paragraph(meta['project_name'], self.styles['CoverMetaVal'])],
                [Paragraph("<b>Target Client Name</b>", self.styles['CoverMetaLabel']), Paragraph(meta['client_name'], self.styles['CoverMetaVal'])],
                [Paragraph("<b>Date Generated</b>", self.styles['CoverMetaLabel']), Paragraph(QDate.currentDate().toString("dd MMM yyyy"), self.styles['CoverMetaVal'])],
                [Paragraph("<b>Project Currency</b>", self.styles['CoverMetaLabel']), Paragraph(f"{symbol} ({meta['currency_symbol']})", self.styles['CoverMetaVal'])],
                [Paragraph("<b>Total Estimate Value</b>", self.styles['CoverMetaLabel']), Paragraph(f"<b>{symbol} {data['total_bid_value']:,.2f}</b>", self.styles['CoverMetaVal'])],
            ]
            meta_box = Table(meta_rows, colWidths=[150, 333])
            meta_box.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                ('PADDING', (0,0), (-1,-1), 10),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(meta_box)
            
            story.append(Spacer(1, 150))
            story.append(Paragraph("<font color='#64748b'><i>This intelligence document compiles cross-project database analytics from priced BOQs, subcontractor adjudications, and parametric benchmarking guides. Confidential under corporate review.</i></font>", self.styles['ExecSubtitle']))
            story.append(PageBreak())
            
            # --- PAGE 2: CFO EXECUTIVE SUMMARY & BRIDGE ---
            story.append(Paragraph("1. CFO Executive Brief", self.styles['SectionHeader']))
            story.append(Paragraph("Consolidated cross-project pricing dashboard showcasing baseline resource net costs, overhead allocations, and expected profitability margins.", self.styles['BodyDesc']))
            story.append(Spacer(1, 10))
            
            # 2x2 KPI Cards
            kpi_table_data = [
                [
                    Paragraph(f"<b>TOTAL GRAND BID</b><br/><font size=16 color='#1b5e20'><b>{symbol} {data['total_bid_value']:,.2f}</b></font><br/><font size=8 color='#64748b'>Gross project bid price</font>", self.styles['KpiCardText']),
                    Paragraph(f"<b>TOTAL NET COST</b><br/><font size=16 color='#0277bd'><b>{symbol} {data['total_net_cost']:,.2f}</b></font><br/><font size=8 color='#64748b'>Base resources cost</font>", self.styles['KpiCardText'])
                ],
                [
                    Paragraph(f"<b>PROFIT MARGIN</b><br/><font size=16 color='#ea580c'><b>{meta['profit_rate']:.2f}%</b></font><br/><font size=8 color='#64748b'>Project target profit</font>", self.styles['KpiCardText']),
                    Paragraph(f"<b>OVERHEAD RATE</b><br/><font size=16 color='#546e7a'><b>{meta['overhead_rate']:.2f}%</b></font><br/><font size=8 color='#64748b'>Operational overhead</font>", self.styles['KpiCardText'])
                ]
            ]
            kpi_table = Table(kpi_table_data, colWidths=[241, 241])
            kpi_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ffffff')),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
                ('BACKGROUND', (0,0), (0,0), colors.HexColor('#f0fdf4')), # light green for grand bid
                ('BACKGROUND', (1,0), (1,0), colors.HexColor('#eff6ff')), # light blue for net cost
                ('BACKGROUND', (0,1), (0,1), colors.HexColor('#fff7ed')), # light orange for profit
                ('BACKGROUND', (1,1), (1,1), colors.HexColor('#f8fafc')), # light grey for overhead
                ('PADDING', (0,0), (-1,-1), 15),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(kpi_table)
            story.append(Spacer(1, 25))
            
            # Net-to-Gross Financial Bridge
            story.append(Paragraph("<b>Net-to-Gross Financial Bridge</b>", self.styles['Normal']))
            story.append(Spacer(1, 5))
            
            combined_markup_pct = (meta['overhead_rate'] + meta['profit_rate']) / 100.0
            overhead_value = data['total_net_cost'] * (meta['overhead_rate'] / 100.0)
            profit_value = data['total_net_cost'] * (meta['profit_rate'] / 100.0)
            
            bridge_rows = [
                [Paragraph("<b>Component Layer</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Factor Rate</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Calculated Amount</b>", self.styles['TableHeaderStyle'])],
                [Paragraph("Base Net Cost", self.styles['TableBodyStyle']), Paragraph("-", self.styles['TableBodyStyle']), Paragraph(f"{symbol} {data['total_net_cost']:,.2f}", self.styles['TableBodyStyleRight'])],
                [Paragraph("Project Overhead Markup", self.styles['TableBodyStyle']), Paragraph(f"+ {meta['overhead_rate']:.2f}%", self.styles['TableBodyStyle']), Paragraph(f"{symbol} {overhead_value:,.2f}", self.styles['TableBodyStyleRight'])],
                [Paragraph("Profit Margin Markup", self.styles['TableBodyStyle']), Paragraph(f"+ {meta['profit_rate']:.2f}%", self.styles['TableBodyStyle']), Paragraph(f"{symbol} {profit_value:,.2f}", self.styles['TableBodyStyleRight'])],
                [Paragraph("<b>FINAL ESTIMATE GRAND TOTAL BID</b>", self.styles['TableBodyStyleBold']), Paragraph("-", self.styles['TableBodyStyleBold']), Paragraph(f"<b>{symbol} {data['total_bid_value']:,.2f}</b>", self.styles['TableBodyStyleBoldRight'])],
            ]
            bridge_table = Table(bridge_rows, colWidths=[230, 100, 153])
            bridge_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#94a3b8')),
                ('LINEBELOW', (0,-2), (-1,-2), 0.5, colors.HexColor('#cbd5e1')),
                ('LINEBELOW', (0,-1), (-1,-1), 1.5, colors.HexColor('#1b5e20')),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f1f8e9')),
                ('PADDING', (0,0), (-1,-1), 6),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(bridge_table)
            story.append(PageBreak())
            
            # --- PAGE 3: PRICING CONFIDENCE & RISK ---
            story.append(Paragraph("2. Pricing Confidence & Risk Analysis", self.styles['SectionHeader']))
            story.append(Paragraph("Evaluates the Pricing Confidence Index (PCI) by source classification. High dependency on manually plugged rates represents premium bid risk.", self.styles['BodyDesc']))
            story.append(Spacer(1, 5))
            
            # Confidence Mix table
            tot_src = sum(data['sources'].values())
            sources_pct = {k: (v / tot_src * 100) if tot_src > 0 else 0.0 for k, v in data['sources'].items()}
            
            mix_rows = [
                [Paragraph("<b>Pricing Mix Source Category</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Confidence Rating</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Priced Volume</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Mix %</b>", self.styles['TableHeaderStyle'])],
                [Paragraph("Gross Rates (SOR / Library Link)", self.styles['TableBodyStyle']), Paragraph("<font color='#166534'><b>HIGH CONFIDENCE</b></font>", self.styles['TableBodyStyle']), Paragraph(f"{symbol} {data['sources']['gross']:,.2f}", self.styles['TableBodyStyleRight']), Paragraph(f"{sources_pct['gross']:.1f}%", self.styles['TableBodyStyleRight'])],
                [Paragraph("Subcontractor Allocations", self.styles['TableBodyStyle']), Paragraph("<font color='#166534'><b>MARKET VERIFIED</b></font>", self.styles['TableBodyStyle']), Paragraph(f"{symbol} {data['sources']['sub']:,.2f}", self.styles['TableBodyStyleRight']), Paragraph(f"{sources_pct['sub']:.1f}%", self.styles['TableBodyStyleRight'])],
                [Paragraph("Manual Plug Rates", self.styles['TableBodyStyle']), Paragraph("<font color='#b45309'><b>HIGH ESTIMATING RISK</b></font>", self.styles['TableBodyStyle']), Paragraph(f"{symbol} {data['sources']['plug']:,.2f}", self.styles['TableBodyStyleRight']), Paragraph(f"{sources_pct['plug']:.1f}%", self.styles['TableBodyStyleRight'])],
                [Paragraph("Provisional Sums", self.styles['TableBodyStyle']), Paragraph("<font color='#475569'>FIXED RISK</font>", self.styles['TableBodyStyle']), Paragraph(f"{symbol} {data['sources']['provisional']:,.2f}", self.styles['TableBodyStyleRight']), Paragraph(f"{sources_pct['provisional']:.1f}%", self.styles['TableBodyStyleRight'])],
                [Paragraph("PC Sums", self.styles['TableBodyStyle']), Paragraph("<font color='#475569'>FIXED RISK</font>", self.styles['TableBodyStyle']), Paragraph(f"{symbol} {data['sources']['pc_sum']:,.2f}", self.styles['TableBodyStyleRight']), Paragraph(f"{sources_pct['pc_sum']:.1f}%", self.styles['TableBodyStyleRight'])],
                [Paragraph("Dayworks", self.styles['TableBodyStyle']), Paragraph("<font color='#991b1b'>VARIABLE COST</font>", self.styles['TableBodyStyle']), Paragraph(f"{symbol} {data['sources']['daywork']:,.2f}", self.styles['TableBodyStyleRight']), Paragraph(f"{sources_pct['daywork']:.1f}%", self.styles['TableBodyStyleRight'])],
                [Paragraph("<b>TOTAL SOURCE COMPOSITION VALUE</b>", self.styles['TableBodyStyleBold']), Paragraph("-", self.styles['TableBodyStyleBold']), Paragraph(f"<b>{symbol} {tot_src:,.2f}</b>", self.styles['TableBodyStyleBoldRight']), Paragraph("100.0%", self.styles['TableBodyStyleBoldRight'])],
            ]
            
            mix_table = Table(mix_rows, colWidths=[180, 120, 110, 73])
            mix_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#94a3b8')),
                ('LINEBELOW', (0,-2), (-1,-2), 0.5, colors.HexColor('#cbd5e1')),
                ('LINEBELOW', (0,-1), (-1,-1), 1.5, colors.HexColor('#1b5e20')),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f8fafc')),
                ('PADDING', (0,0), (-1,-1), 5),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(mix_table)
            story.append(Spacer(1, 20))
            
            # Flagged Items & Progress Stats
            progress_pct = (data['priced_items'] / data['total_items'] * 100) if data['total_items'] > 0 else 0.0
            
            story.append(Paragraph("<b>Pricing Progress & Review Flags Summary</b>", self.styles['Normal']))
            story.append(Spacer(1, 5))
            
            stat_rows = [
                [Paragraph("Total Quantified BOQ Items", self.styles['TableBodyStyle']), Paragraph(str(data['total_items']), self.styles['TableBodyStyleRight']), Paragraph("Priced Progress Ratio", self.styles['TableBodyStyle']), Paragraph(f"<b>{progress_pct:.2f}%</b>", self.styles['TableBodyStyleRight'])],
                [Paragraph("Total Priced BOQ Items", self.styles['TableBodyStyle']), Paragraph(str(data['priced_items']), self.styles['TableBodyStyleRight']), Paragraph("Flagged Outliers Logged", self.styles['TableBodyStyle']), Paragraph(f"<font color='#991b1b'><b>{data['flagged_items']} Flags</b></font>", self.styles['TableBodyStyleRight'])],
            ]
            stat_table = Table(stat_rows, colWidths=[150, 90, 150, 93])
            stat_table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
                ('PADDING', (0,0), (-1,-1), 6),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(stat_table)
            
            # List some of the flagged outlier items if there are any
            flagged_list = [item for item in data['all_items_flat'] if item['flagged']][:5]
            if flagged_list:
                story.append(Spacer(1, 15))
                story.append(Paragraph("<b>Outlier Audit Flags (Top 5 deviating rates):</b>", self.styles['Normal']))
                story.append(Spacer(1, 5))
                flag_rows = [
                    [Paragraph("<b>Item Description</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Sheet Component</b>", self.styles['TableHeaderStyle']), Paragraph("<b>BOQ Unit Cost</b>", self.styles['TableHeaderStyle'])]
                ]
                for f_item in flagged_list:
                    flag_rows.append([
                        Paragraph(f_item['desc'][:50], self.styles['TableBodyStyle']),
                        Paragraph(f_item['sheet'], self.styles['TableBodyStyle']),
                        Paragraph(f"{symbol} {f_item['unit_cost']:,.2f}", self.styles['TableBodyStyleRight'])
                    ])
                flag_table = Table(flag_rows, colWidths=[230, 150, 103])
                flag_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#fee2e2')),
                    ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#ef4444')),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                    ('PADDING', (0,0), (-1,-1), 4),
                ]))
                story.append(flag_table)
            story.append(PageBreak())
            
            # --- PAGE 4: PARETO COST DRIVERS & MATERIAL BOM ---
            story.append(Paragraph("3. Top Value Drivers & Material BOM", self.styles['SectionHeader']))
            story.append(Paragraph("Visualizes the 20% of BOQ items that represent 80% of project costs, alongside operational quantities aggregated from composite buildups.", self.styles['BodyDesc']))
            story.append(Spacer(1, 5))
            
            # Pareto Table (Top 8 drivers)
            story.append(Paragraph("<b>Top Pareto Value Cost Drivers</b>", self.styles['Normal']))
            story.append(Spacer(1, 5))
            
            pareto_list = sorted(data['all_items_flat'], key=lambda x: x['total_cost'], reverse=True)[:8]
            pareto_rows = [
                [Paragraph("<b>Rank</b>", self.styles['TableHeaderStyle']), Paragraph("<b>BOQ Item Description</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Qty</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Unit Rate</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Final Bid Total</b>", self.styles['TableHeaderStyle'])],
            ]
            for idx, p_item in enumerate(pareto_list, 1):
                item_bid_total = p_item.get('total_bid', p_item['total_cost'] * (1.0 + combined_markup_pct))
                item_bid_rate = item_bid_total / p_item['qty'] if p_item['qty'] > 0 else p_item['unit_cost']
                pareto_rows.append([
                    Paragraph(f"#{idx}", self.styles['TableBodyStyleBold']),
                    Paragraph(p_item['desc'][:60] + ("..." if len(p_item['desc']) > 60 else ""), self.styles['TableBodyStyle']),
                    Paragraph(f"{p_item['qty']:,.1f}", self.styles['TableBodyStyleRight']),
                    Paragraph(f"{symbol} {item_bid_rate:,.2f}", self.styles['TableBodyStyleRight']),
                    Paragraph(f"<b>{symbol} {item_bid_total:,.2f}</b>", self.styles['TableBodyStyleRight']),
                ])
                
            pareto_table = Table(pareto_rows, colWidths=[30, 210, 50, 93, 100])
            pareto_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#94a3b8')),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                ('PADDING', (0,0), (-1,-1), 4),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(pareto_table)
            story.append(Spacer(1, 15))
            
            # BOM Materials Table
            story.append(Paragraph("<b>Aggregated Material Volumes (Operational BOM)</b>", self.styles['Normal']))
            story.append(Spacer(1, 5))
            
            bom_list = sorted(data['materials'].values(), key=lambda x: x['cost'], reverse=True)[:8]
            mat_total = sum(m['cost'] for m in data['materials'].values())
            bom_rows = [
                [Paragraph("<b>Resource Name</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Unit</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Total Volume Qty</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Avg Rate</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Estimated Cost</b>", self.styles['TableHeaderStyle'])],
            ]
            for m in bom_list:
                avg_rate = m['cost'] / m['qty'] if m['qty'] > 0 else 0
                bom_rows.append([
                    Paragraph(m['name'][:40], self.styles['TableBodyStyle']),
                    Paragraph(m['unit'], self.styles['TableBodyStyle']),
                    Paragraph(f"{m['qty']:,.2f}", self.styles['TableBodyStyleRight']),
                    Paragraph(f"{symbol} {avg_rate:,.2f}", self.styles['TableBodyStyleRight']),
                    Paragraph(f"{symbol} {m['cost']:,.2f}", self.styles['TableBodyStyleRight']),
                ])
            bom_rows.append([
                Paragraph("<b>TOTAL MAJOR MATERIAL VOLUME BUDGET</b>", self.styles['TableBodyStyleBold']),
                Paragraph("", self.styles['TableBodyStyle']),
                Paragraph("", self.styles['TableBodyStyle']),
                Paragraph("", self.styles['TableBodyStyle']),
                Paragraph(f"<b>{symbol} {mat_total:,.2f}</b>", self.styles['TableBodyStyleBoldRight']),
            ])
            
            bom_table = Table(bom_rows, colWidths=[180, 50, 80, 73, 100])
            bom_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#94a3b8')),
                ('LINEBELOW', (0,-2), (-1,-2), 0.5, colors.HexColor('#cbd5e1')),
                ('LINEBELOW', (0,-1), (-1,-1), 1.5, colors.HexColor('#1b5e20')),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f8fafc')),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                ('PADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(bom_table)
            story.append(PageBreak())
            
            # --- PAGE 5: ADJUDICATION & COST MODELLING ---
            story.append(Paragraph("4. Supply Chain & Cost Modelling Benchmarking", self.styles['SectionHeader']))
            story.append(Paragraph("Audits subcontractor package commitments against internal target estimates, and presents cost per square meter benchmarking.", self.styles['BodyDesc']))
            story.append(Spacer(1, 5))
            
            # Adjudication table
            story.append(Paragraph("<b>Supply Chain Package Commitments & Variances</b>", self.styles['Normal']))
            story.append(Spacer(1, 5))
            
            adj_rows = [
                [Paragraph("<b>Package Name</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Awarded Subcontractor</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Award Value</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Target Budget</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Variance</b>", self.styles['TableHeaderStyle'])],
            ]
            for pkg in data['adjudication'][:6]:
                target = pkg['target_val']
                winner_val = pkg['winner_val']
                variance = target - winner_val
                var_pct = (variance / target * 100) if target > 0 else 0
                v_color = "#166534" if variance >= 0 else "#991b1b"
                v_txt = f"<font color='{v_color}'><b>{var_pct:+.1f}%</b></font>"
                
                adj_rows.append([
                    Paragraph(pkg['package_name'][:25], self.styles['TableBodyStyle']),
                    Paragraph(pkg['winner_name'][:20], self.styles['TableBodyStyle']),
                    Paragraph(f"{symbol} {winner_val:,.2f}", self.styles['TableBodyStyleRight']),
                    Paragraph(f"{symbol} {target:,.2f}", self.styles['TableBodyStyleRight']),
                    Paragraph(v_txt, self.styles['TableBodyStyleRight']),
                ])
            adj_rows.append([
                Paragraph("<b>TOTAL SUBCONTRACT COMMITMENTS</b>", self.styles['TableBodyStyleBold']),
                Paragraph("", self.styles['TableBodyStyle']),
                Paragraph(f"<b>{symbol} {data['sub_alloc']:,.2f}</b>", self.styles['TableBodyStyleBoldRight']),
                Paragraph("", self.styles['TableBodyStyle']),
                Paragraph("", self.styles['TableBodyStyle']),
            ])
            
            adj_table = Table(adj_rows, colWidths=[130, 110, 80, 80, 83])
            adj_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#94a3b8')),
                ('LINEBELOW', (0,-2), (-1,-2), 0.5, colors.HexColor('#cbd5e1')),
                ('LINEBELOW', (0,-1), (-1,-1), 1.5, colors.HexColor('#1b5e20')),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f8fafc')),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                ('PADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(adj_table)
            story.append(Spacer(1, 15))
            
            # GFA Benchmarking Table
            story.append(Paragraph("<b>Gross Floor Area (GFA) Parametric Benchmarking</b>", self.styles['Normal']))
            story.append(Spacer(1, 5))
            
            bench = data['benchmark']
            bench_rows = [
                [Paragraph("<b>Parametric Variable</b>", self.styles['TableHeaderStyle']), Paragraph("<b>Configured Simulation Model Settings</b>", self.styles['TableHeaderStyle'])],
                [Paragraph("Building Target Type", self.styles['TableBodyStyle']), Paragraph(bench['b_type'], self.styles['TableBodyStyle'])],
                [Paragraph("Regional Pricing Factor", self.styles['TableBodyStyle']), Paragraph(bench['region'], self.styles['TableBodyStyle'])],
                [Paragraph("Quality Finish Specification", self.styles['TableBodyStyle']), Paragraph(bench['spec'], self.styles['TableBodyStyle'])],
                [Paragraph("Architectural Complexity", self.styles['TableBodyStyle']), Paragraph(bench['complexity'], self.styles['TableBodyStyle'])],
                [Paragraph("Site & Ground Conditions", self.styles['TableBodyStyle']), Paragraph(bench['site'], self.styles['TableBodyStyle'])],
                [Paragraph("Configured GFA Volume", self.styles['TableBodyStyle']), Paragraph(f"<b>{bench['gfa']:,.1f} m²</b>", self.styles['TableBodyStyle'])],
                [Paragraph("Simulated Target $/m² Rate", self.styles['TableBodyStyle']), Paragraph(f"<b>{symbol} {bench['simulated_rate']:,.2f} / m²</b>", self.styles['TableBodyStyle'])],
                [Paragraph("Actual Bid Project $/m² Rate", self.styles['TableBodyStyleBold']), Paragraph(f"<font color='#1b5e20'><b>{symbol} {bench['actual_rate']:,.2f} / m²</b></font> (Based on {symbol} {data['total_bid_value']:,.1f})", self.styles['TableBodyStyleBold'])],
            ]
            
            bench_table = Table(bench_rows, colWidths=[180, 303])
            bench_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#94a3b8')),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#e8f5e9')),
                ('PADDING', (0,0), (-1,-1), 5),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(bench_table)
            
            # 7. Build Document
            doc.build(story, canvasmaker=NumberedCanvas)
            return True
        except Exception as e:
            print(f"Executive PDF Generation Error: {e}")
            import traceback
            traceback.print_exc()
            return False
