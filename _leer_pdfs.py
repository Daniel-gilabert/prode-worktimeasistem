import pdfplumber, sys
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("PDF GLOBAL")
print("=" * 60)
with pdfplumber.open(r'C:\Users\ADMON121_\Downloads\Resumen_Global_Asistencia_Diciembre_2025 (2).pdf') as pdf:
    print(f'Paginas: {len(pdf.pages)}')
    for i, p in enumerate(pdf.pages[:3]):
        print(f'\n--- PAGINA {i+1} ---')
        print(p.extract_text())

print("\n" + "=" * 60)
print("PDF INDIVIDUAL")
print("=" * 60)
with pdfplumber.open(r'C:\Users\ADMON121_\Downloads\Asistencia_AGENJO_BEJARANO_JUAN_MANUEL_2025_12 (19).pdf') as pdf:
    print(f'Paginas: {len(pdf.pages)}')
    for i, p in enumerate(pdf.pages[:3]):
        print(f'\n--- PAGINA {i+1} ---')
        print(p.extract_text())
