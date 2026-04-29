import pandas as pd
import traceback
import sys

f = r'C:\Users\Consar-Kilpatrick\Desktop\Apinto_LOADED\Apinto_Hospital\Imported BOQs\BILL NR 11 VAC INSTALLATION rv2.xls'
print(f"Reading {f}")
try:
    xl = pd.ExcelFile(f)
    print(xl.sheet_names)
except Exception as e:
    print(traceback.format_exc())
