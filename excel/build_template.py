"""Create an editable Aurelis monthly business performance workbook."""
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.chart import LineChart, Reference
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule

OUT = Path(__file__).resolve().parent / "Aurelis_Business_Performance_Template.xlsx"
wb = Workbook(); ws = wb.active; ws.title = "Monthly Inputs"
navy="14221F"; lime="C9E56A"; ivory="F4F1E8"; grey="E8EBE2"
ws.sheet_view.showGridLines = False
ws.merge_cells("A1:H1"); ws["A1"]="AURELIS | BUSINESS PERFORMANCE MODEL"; ws["A1"].font=Font(name="Aptos Display",size=16,bold=True,color="FFFFFF"); ws["A1"].fill=PatternFill("solid",fgColor=navy); ws["A1"].alignment=Alignment(vertical="center"); ws.row_dimensions[1].height=34
ws.merge_cells("A2:H2"); ws["A2"]="Enter monthly figures in the yellow input cells. Formula columns calculate automatically. Replace sample values before using."; ws["A2"].font=Font(italic=True,color="657064",size=10); ws.row_dimensions[2].height=25
headers=["Month","Revenue (₹)","COGS (₹)","Operating expenses (₹)","Gross profit (₹)","Operating profit (₹)","Gross margin (%)","Operating margin (%)"]
for c,h in enumerate(headers,1):
    cell=ws.cell(4,c,h); cell.font=Font(bold=True,color="FFFFFF",size=9); cell.fill=PatternFill("solid",fgColor=navy); cell.alignment=Alignment(wrap_text=True,vertical="center")
ws.row_dimensions[4].height=34
months=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
for r,m in enumerate(months,5):
    ws.cell(r,1,m)
    for col,val in [(2,850000),(3,390000),(4,270000)]:
        cell=ws.cell(r,col,val if r==5 else 0); cell.fill=PatternFill("solid",fgColor="FFF4CC"); cell.number_format='₹#,##0;[Red](₹#,##0);-'
    ws.cell(r,5,f'=B{r}-C{r}'); ws.cell(r,6,f'=E{r}-D{r}'); ws.cell(r,7,f'=IFERROR(E{r}/B{r},0)'); ws.cell(r,8,f'=IFERROR(F{r}/B{r},0)')
    for col in range(5,9): ws.cell(r,col).fill=PatternFill("solid",fgColor="EAF0DD")
    for col in (5,6): ws.cell(r,col).number_format='₹#,##0;[Red](₹#,##0);-'
    for col in (7,8): ws.cell(r,col).number_format='0.0%'
    for col in range(1,9): ws.cell(r,col).border=Border(bottom=Side(style="hair",color="DDE1D7"))
ws.freeze_panes="B5"; ws.auto_filter.ref="A4:H16"
for col,width in {"A":13,"B":18,"C":18,"D":23,"E":19,"F":21,"G":17,"H":20}.items(): ws.column_dimensions[col].width=width
ws2=wb.create_sheet("Summary"); ws2.sheet_view.showGridLines=False
ws2.merge_cells("A1:D1"); ws2["A1"]="AURELIS | MANAGEMENT SUMMARY"; ws2["A1"].font=Font(bold=True,size=16,color="FFFFFF"); ws2["A1"].fill=PatternFill("solid",fgColor=navy); ws2.row_dimensions[1].height=34
metrics=[("Metric","Formula / result"),("Total revenue","=SUM('Monthly Inputs'!B5:B16)"),("Gross profit","=SUM('Monthly Inputs'!E5:E16)"),("Operating profit","=SUM('Monthly Inputs'!F5:F16)"),("Gross margin","=IFERROR(B3/B2,0)"),("Operating margin","=IFERROR(B4/B2,0)"),("Average monthly revenue","=AVERAGE('Monthly Inputs'!B5:B16)")]
for r,row in enumerate(metrics,3):
    for c,v in enumerate(row,1):
        cell=ws2.cell(r,c,v); cell.fill=PatternFill("solid",fgColor=navy if r==3 else ("EAF0DD" if c==2 else "F4F1E8")); cell.font=Font(bold=(r==3 or c==1),color="FFFFFF" if r==3 else navy); cell.alignment=Alignment(vertical="center")
for r in (4,5,6,9): ws2.cell(r,2).number_format='₹#,##0;[Red](₹#,##0);-'
for r in (7,8): ws2.cell(r,2).number_format='0.0%'
ws2.column_dimensions["A"].width=30; ws2.column_dimensions["B"].width=25
chart=LineChart(); chart.title="Monthly Revenue & Operating Profit"; chart.y_axis.title="INR"; chart.x_axis.title="Month"; chart.style=13; chart.height=8; chart.width=17
chart.add_data(Reference(ws,min_col=2,max_col=2,min_row=4,max_row=16),titles_from_data=True); chart.add_data(Reference(ws,min_col=6,max_col=6,min_row=4,max_row=16),titles_from_data=True); chart.set_categories(Reference(ws,min_col=1,min_row=5,max_row=16)); ws2.add_chart(chart,"D3")
ws3=wb.create_sheet("Read Me"); ws3.sheet_view.showGridLines=False
notes=[("AURELIS MODEL GUIDE", ""),("Purpose","Simple monthly P&L tracker and management summary."),("Yellow cells","Editable inputs: revenue, cost of goods sold and operating expenses."),("Green cells","Calculated outputs. Do not overwrite formulas."),("Gross profit","Revenue less cost of goods sold (COGS)."),("Operating profit","Gross profit less operating expenses. This simplified model excludes finance costs, tax, depreciation and other adjustments."),("Important","This template is an educational starting point, not audited financial statements or professional tax/accounting advice."),("Use","Replace sample data, check that all months use the same accounting basis and reconcile totals to source records.")]
for r,(a,b) in enumerate(notes,1):
    ws3.cell(r,1,a).font=Font(bold=True,color="FFFFFF" if r==1 else navy); ws3.cell(r,1).fill=PatternFill("solid",fgColor=navy if r==1 else ivory); ws3.cell(r,2,b).alignment=Alignment(wrap_text=True,vertical="top"); ws3.row_dimensions[r].height=30 if r>1 else 34
ws3.column_dimensions["A"].width=22; ws3.column_dimensions["B"].width=105
wb.save(OUT); print(OUT)
