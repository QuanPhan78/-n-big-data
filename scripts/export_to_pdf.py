import win32com.client
import os
import sys

docx_path = os.path.abspath("Bao_Cao_Do_An_BigData_NYC_2025.docx")
pdf_path = os.path.abspath("Bao_Cao_Do_An_BigData_NYC_2025.pdf")

if not os.path.exists(docx_path):
    print("Error: File not found:", docx_path)
    sys.exit(1)

print("Opening Word Application...")
word = win32com.client.DispatchEx("Word.Application")
word.Visible = False
word.DisplayAlerts = False

try:
    print("Opening docx:", docx_path)
    doc = word.Documents.Open(docx_path, ReadOnly=True)
    print("Saving as PDF:", pdf_path)
    doc.SaveAs(pdf_path, FileFormat=17) # 17 is wdFormatPDF
    doc.Close(SaveChanges=False)
    print("Done! PDF size:", os.path.getsize(pdf_path), "bytes")
finally:
    word.Quit()
