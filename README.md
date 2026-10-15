# ⚡ VEDANSHU — Product Packet Analyser

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white"/>
  <img src="https://img.shields.io/badge/Tesseract-OCR-green?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Status-Complete-34D399?style=for-the-badge"/>
</p>

<p align="center">
  <strong>An AI-powered food label analysis platform that extracts, evaluates, and scores packaged food products from a single photo.</strong>
</p>

---

## 🧠 What Is Analyzer?

VEDANSHU takes a **photo of any packaged food product** and runs it through a full analysis pipeline:

- **OCR** reads the label text using Tesseract
- **Parser** extracts 19 fields — product name, brand, MRP, dates, ingredients, 11 nutrients
- **Health Score** computes a real 0–100 grade using NHS/FSSAI thresholds
- **Risk Engine** flags HIGH/MODERATE/OK nutrients and dangerous ingredient categories
- **Allergen Detector** checks 13 allergen categories against the ingredients list
- **Export** lets you download a PDF report or CSV spreadsheet

> 💡 No Tesseract installed? Click **"Sample Demo Packet"** on the landing page — the full pipeline runs on built-in sample data.

---

## 🖥️ Screenshots / Screens

| Screen | What It Shows |
|--------|--------------|
| 🏠 **Landing** | Hero section, 6 feature cards, how-it-works, live health score preview |
| 📡 **Scanner** | Holographic upload chamber — drag & drop your product image |
| 📊 **Results** | Health score, nutrition matrix, risk alerts, allergen detection, PDF/CSV export |
| 🕓 **History** | Session log of every scan with grades and alert summaries |

---

## ✅ Features

| Feature | Details |
|---------|---------|
| **OCR Pipeline** | Tesseract 5.x · multi-PSM (6, 4, 11, 3) · LSTM engine · auto-path detection |
| **Text Extraction** | 19 regex-based fields including 11 nutrition values |
| **Health Score** | Weighted 0–100 formula across 6 nutrients · Grade A / B / C / D |
| **Risk Alerts** | NHS traffic-light thresholds · HIGH / MODERATE / OK / UNKNOWN |
| **Ingredient Flags** | 10 categories: palm oil, trans fats, artificial colours, preservatives, HFCS, MSG & more |
| **Allergen Detection** | 13 categories: Gluten, Dairy, Peanuts, Tree Nuts, Soy, Eggs, Fish, Crustaceans, Sesame, Mustard, Sulphites, Celery, Molluscs |
| **PDF Export** | Formatted A4 report via ReportLab with colour-coded tables |
| **CSV Export** | 6-section spreadsheet, Excel-compatible (UTF-8 BOM) |
| **Scan History** | Session log — compare past scans without re-uploading |
| **Demo Mode** | Works fully without Tesseract using built-in sample data |

---

## 🏗️ Project Structure

```
VEDANSHU/
│
├── app.py                        ← Streamlit entry point (4-screen router)
├── requirements.txt
├── README.md
├── test_backend.py               ← 74-test backend suite
├── diag_pipeline.py              ← Standalone diagnostic script
│
├── .streamlit/
│   └── config.toml               ← Dark theme + server config
│
├── backend/                      ← All business logic
│   ├── __init__.py
│   ├── allergen_engine.py        ← 13 allergen categories
│   ├── export_engine.py          ← PDF (ReportLab) + CSV generation
│   ├── extractor.py              ← Regex parser — 19 fields + 11 nutrients
│   ├── health_score.py           ← Real 0–100 weighted score formula
│   ├── image_utils.py            ← Validation + 6-step OpenCV preprocessing
│   ├── nutrition_rules.py        ← NHS/FSSAI threshold evaluations
│   ├── ocr_utils.py              ← Tesseract multi-PSM + OCR text cleaning
│   ├── risk_engine.py            ← Quantitative alerts + ingredient flags
│   └── scan_history.py           ← Session-scoped scan log
│
└── frontend/                     ← UI components + design system
    ├── __init__.py
    ├── components.py             ← Health score, allergen & history panels
    └── styles.css                ← Dark glassmorphism design system
```

---

## 💯 Health Score Formula

Six nutrients contribute a component score (0–100), combined as a weighted sum:

| Nutrient | Weight | Type | OK ✅ | HIGH 🔴 |
|---|---|---|---|---|
| Sugar | 20% | Penalty | ≤ 5g / 100g | ≥ 22.5g / 100g |
| Saturated Fat | 20% | Penalty | ≤ 1.5g / 100g | ≥ 5g / 100g |
| Trans Fat | 15% | Penalty | ≤ 0.2g / 100g | ≥ 2g / 100g |
| Sodium | 15% | Penalty | ≤ 300mg / 100g | ≥ 600mg / 100g |
| Protein | 15% | Reward | ≥ 10g / 100g | ≤ 5g / 100g |
| Dietary Fibre | 15% | Reward | ≥ 6g / 100g | ≤ 3g / 100g |

**Grade Bands:**

| Score | Grade | Label |
|---|---|---|
| ≥ 75 | 🟢 A | Healthy |
| ≥ 55 | 🔵 B | Acceptable |
| ≥ 35 | 🟡 C | Moderate Concern |
| < 35 | 🔴 D | High Concern |

> Undetected nutrients contribute a neutral 50/100 (neither penalised nor rewarded).

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/vedanshu-product-analyser.git
cd vedanshu-product-analyser
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Tesseract OCR *(for real image scanning)*

**Windows:**
1. Download the installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
2. Choose `tesseract-ocr-w64-setup-5.x.x.exe` (64-bit)
3. Install to the default path: `C:\Program Files\Tesseract-OCR\`
4. Restart your terminal

**Linux:**
```bash
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

---

## 🚀 Run the App

```bash
streamlit run app.py
```

Then open `http://localhost:8501` in your browser.

---

## 📦 Dependencies

```
streamlit>=1.30.0
Pillow>=10.0.0
pandas>=2.0.0
pytesseract>=0.3.10
opencv-python>=4.8.0
numpy>=1.24.0
reportlab>=4.0.0
```

---

## 📐 Reference Standards

| Standard | Used For |
|----------|----------|
| **NHS UK** Traffic-Light Labelling | Sugar, Fat, Saturated Fat, Salt, Sodium thresholds |
| **FSSAI** Draft Regulations 2022 | Trans Fat limit (≤ 2g per 100g) |
| **WHO** Recommendations | Sodium daily intake, Trans Fat elimination |
| **ICMR** Guidelines | Added sugar daily limits |
| **EU FIC Regulation 1169/2011** | Allergen labelling categories |
| **FDA FALCPA** | Major food allergen reference |

---

## ⚠️ Disclaimer

All outputs are for **informational and educational purposes only.**
They are not a medical diagnosis, dietary prescription, or safety verdict.
Always verify information on the physical product label.
Consult a registered dietitian for personal dietary advice.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| UI Framework | Streamlit |
| OCR Engine | Tesseract 5.x via pytesseract |
| Image Processing | OpenCV 4.x + Pillow |
| PDF Export | ReportLab 5.x |
| Data Processing | pandas + numpy |
| Fonts | Space Grotesk · JetBrains Mono · Inter |
| Language | Python 3.9+ |

---

<p align="center">
  Made with ❤️ · VEDANSHU Product Packet Analyser · Minor Project · Not medical advice
</p>
