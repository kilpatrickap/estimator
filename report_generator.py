from PyQt6.QtGui import QTextDocument, QFont, QPageSize
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtCore import QSizeF, QDate
import sys


class ReportGenerator:
    def __init__(self, estimate):
        self.estimate = estimate

    def generate_html(self, company_name=""):
        totals = self.estimate.calculate_totals()
        symbol = self.estimate.currency.split('(')[-1].strip(')') if '(' in self.estimate.currency else '$'
        date_str = self.estimate.date.split()[0] if self.estimate.date else "N/A"

        # Basic HTML Template
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; color: #333; }}
                h1 {{ color: #2e7d32; border-bottom: 2px solid #2e7d32; padding-bottom: 10px; }}
                h2 {{ color: #2e7d32; margin-top: 20px; }}
                .meta {{ margin-bottom: 30px; font-size: 14px; }}
                .meta table {{ width: 100%; }}
                .meta td {{ padding: 5px; }}
                table.items {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                table.items th {{ background-color: #f5f5f5; padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                table.items td {{ padding: 10px; border-bottom: 1px solid #eee; }}
                .total-row td {{ font-weight: bold; background-color: #f9f9f9; }}
                .grand-total {{ font-size: 18px; font-weight: bold; color: #2e7d32; padding-top: 20px; text-align: right; }}
                .footer {{ margin-top: 50px; font-size: 12px; color: #777; text-align: center; border-top: 1px solid #eee; padding-top: 10px; }}
            </style>
        </head>
        <body>
            <h1>Construction Estimate</h1>
        """

        if company_name:
            html += f"<h3>{company_name}</h3>"

        html += f"""
            <div class="meta">
                <table>
                    <tr>
                        <td><strong>Project:</strong> {self.estimate.project_name}</td>
                        <td><strong>Date:</strong> {date_str}</td>
                    </tr>
                    <tr>
                        <td><strong>Client/Location:</strong> {self.estimate.client_name}</td>
                        <td><strong>Reference ID:</strong> #{self.estimate.id if self.estimate.id else 'New'}</td>
                    </tr>
                </table>
            </div>
        """

        for i, task in enumerate(self.estimate.tasks, 1):
            html += f"<h2>Task {i}: {task.description}</h2>"
            
            # Combine all items into one list for cleaner printing
            items = []
            for m in task.materials:
                items.append(("Material", m['name'], f"{m['qty']} {m['unit']}", m['unit_cost'], m['total']))
            for l in task.labor:
                items.append(("Labor", l['trade'], f"{l['hours']} hrs", l['rate'], l['total']))
            for e in task.equipment:
                items.append(("Equipment", e['name'], f"{e['hours']} hrs", e['rate'], e['total']))

            if items:
                html += """
                <table class="items">
                    <tr>
                        <th width="15%">Type</th>
                        <th width="35%">Description</th>
                        <th width="20%">Quantity</th>
                        <th width="15%">Rate</th>
                        <th width="15%">Total</th>
                    </tr>
                """
                for type_, desc, qty, rate, total in items:
                    html += f"""
                    <tr>
                        <td>{type_}</td>
                        <td>{desc}</td>
                        <td>{qty}</td>
                        <td>{symbol}{rate:,.2f}</td>
                        <td>{symbol}{total:,.2f}</td>
                    </tr>
                    """
                html += f"""
                    <tr class="total-row">
                        <td colspan="4" style="text-align: right;">Task Subtotal:</td>
                        <td>{symbol}{task.get_subtotal():,.2f}</td>
                    </tr>
                </table>
                """
            else:
                html += "<p>No items in this task.</p>"

        # Summary
        html += f"""
            <div style="page-break-inside: avoid;">
                <h2>Summary</h2>
                <table style="width: 50%; margin-left: auto;">
                    <tr>
                        <td>Subtotal:</td>
                        <td style="text-align: right;">{symbol}{totals['subtotal']:,.2f}</td>
                    </tr>
                    <tr>
                        <td>Overhead ({self.estimate.overhead_percent}%):</td>
                        <td style="text-align: right;">{symbol}{totals['overhead']:,.2f}</td>
                    </tr>
                    <tr>
                        <td>Profit Margin ({self.estimate.profit_margin_percent}%):</td>
                        <td style="text-align: right;">{symbol}{totals['profit']:,.2f}</td>
                    </tr>
                    <tr style="height: 20px;"></tr>
                    <tr>
                        <td class="grand-total">GRAND TOTAL:</td>
                        <td class="grand-total" style="text-align: right;">{symbol}{totals['grand_total']:,.2f}</td>
                    </tr>
                </table>
            </div>

            <div class="footer">
                Generated by Estimator Pro on {QDate.currentDate().toString('dd MMM yyyy')}
            </div>
        </body>
        </html>
        """
        return html

    def export_to_pdf(self, filename, company_name=""):
        doc = QTextDocument()
        html = self.generate_html(company_name)
        doc.setHtml(html)

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(filename)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        
        doc.print(printer)
        return True
