import zipfile
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = r"D:\BigData\nyc_ridehailing_bigdata"
ZIP_PATH = os.path.join(ROOT_DIR, "Bao_Cao_Tien_Do_BigData_PhanMinhQuan.zip")
PDF_PATH = os.path.join(ROOT_DIR, "Bao_Cao_Do_An_BigData_NYC_2025.pdf")
DOCX_PATH = os.path.join(ROOT_DIR, "Bao_Cao_Do_An_BigData_NYC_2025.docx")

if os.path.exists(ZIP_PATH):
    os.remove(ZIP_PATH)

print("Đang đóng gói hồ sơ nộp đồ án chuẩn vào ZIP...")

with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
    # 1. Báo cáo PDF chính
    if os.path.exists(PDF_PATH):
        zipf.write(PDF_PATH, "Bao_Cao_Do_An_BigData_NYC_2025.pdf")
        print(f"  + Added: Bao_Cao_Do_An_BigData_NYC_2025.pdf ({os.path.getsize(PDF_PATH)} bytes)")
    
    # 2. Báo cáo Word DOCX (dự phòng)
    if os.path.exists(DOCX_PATH):
        zipf.write(DOCX_PATH, "Bao_Cao_Do_An_BigData_NYC_2025.docx")
        print(f"  + Added: Bao_Cao_Do_An_BigData_NYC_2025.docx ({os.path.getsize(DOCX_PATH)} bytes)")

    # 3. README & Cấu hình Docker
    for f in ["README.md", "docker-compose.yml", "requirements.txt", ".env.example"]:
        fp = os.path.join(ROOT_DIR, f)
        if os.path.exists(fp):
            zipf.write(fp, f"source_code/{f}")
            print(f"  + Added: source_code/{f}")

    # 4. Source code các thư mục cốt lõi
    folders = ["spark", "ml", "dashboard", "streaming", "airflow", "scripts"]
    for folder in folders:
        folder_path = os.path.join(ROOT_DIR, folder)
        if os.path.exists(folder_path):
            for root, dirs, files in os.walk(folder_path):
                # Bỏ qua các file tạm/test
                for file in files:
                    if file.endswith(('.py', '.sql', '.sh', '.ps1', '.json', '.yaml', '.yml')) and not file.startswith(('test_', 'patch_', 'diagnose_', 'do_splice', 'fix_')):
                        full_p = os.path.join(root, file)
                        rel_p = os.path.relpath(full_p, ROOT_DIR)
                        zipf.write(full_p, f"source_code/{rel_p.replace(os.sep, '/')}")

    # 5. Output minh chứng kết quả (SQL, ML metrics)
    output_dir = os.path.join(ROOT_DIR, "output")
    if os.path.exists(output_dir):
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                if file.endswith(('.csv', '.json', '.txt')):
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, ROOT_DIR)
                    zipf.write(full_p, f"evidence_output/{rel_p.replace(os.sep, '/')}")

print(f"Đóng gói thành công: {ZIP_PATH} | Dung lượng: {os.path.getsize(ZIP_PATH)} bytes (~{round(os.path.getsize(ZIP_PATH)/(1024*1024), 2)} MB)")
