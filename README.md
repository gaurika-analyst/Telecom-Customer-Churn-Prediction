# 📡 Telecom Customer Churn Prediction & Business Analytics

An end-to-end machine-learning and business-intelligence application that predicts customer churn, surfaces actionable retention strategies, and presents everything through an interactive Dash dashboard — all in a single Python file.

---

## 🌐 Dataset

| Property | Detail |
|---|---|
| Source | [Telco Customer Churn – Kaggle](https://www.kaggle.com/datasets/blastchar/telco-customer-churn) |
| File | `telecom_churn.csv` |
| Rows | 7,043 customers |
| Columns | 21 features (demographics, services, charges, churn label) |

---

## 🏗️ Project Structure

```
Telecom_Churn_Project/
├── GaurikaDogra_TelecomChurn.py    ← Single-file ML backend + Dash frontend
├── telecom_churn.csv       ← Dataset (place here before running)
├── requirements.txt        ← All Python dependencies
├── README.md               ← This file
└── GaurikaDogra_ProjectReport.docx  ← Detailed project report
```

---

## ⚡ Quickstart

### 1 · Clone / download the project

```bash
git clone <your-repo-url>
cd Telecom_Churn_Project
```

### 2 · Create and activate a virtual environment *(recommended)*

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3 · Install dependencies

```bash
pip install -r requirements.txt
```

### 4 · Place the dataset

Download `telecom_churn.csv` from [Kaggle](https://www.kaggle.com/datasets/blastchar/telco-customer-churn) and place it in the project root (same directory as `app.py`).

### 5 · Run the application

```bash
python GaurikaDogra_TelecomChurn.py
```

The console will print a summary, then open the dashboard at:

```
http://127.0.0.1:8050
```

---

## 📊 Dashboard Tabs

| Tab | What you'll see |
|---|---|
| **🏢 Executive KPIs** | Total customers, churn rate, revenue at risk, risk-segment breakdown, monthly-charges distribution |
| **📊 Churn Risk Drivers** | Churn by contract type, tenure bucket, internet service, payment method, feature importances, scatter plot |
| **🤖 Model Performance** | Side-by-side comparison of Logistic Regression, Random Forest, Gradient Boosting — accuracy, precision, recall, F1, ROC-AUC, confusion matrices |
| **🎯 Retention Strategies** | Five actionable retention playbooks + sortable/filterable top-50 high-risk customer table |

---

## 🤖 ML Pipeline

1. **Preprocessing** — numeric coercion for `TotalCharges`, median imputation, label encoding, standard scaling
2. **Models trained**
   - Logistic Regression (scaled features, `max_iter=1000`)
   - Random Forest (200 trees, parallel)
   - Gradient Boosting (200 estimators)
3. **Evaluation** — 80/20 stratified split; metrics: Accuracy, Precision, Recall, F1, ROC-AUC
4. **Best model** is auto-selected by F1 score and used for full-dataset scoring
5. **Risk segments** — High (≥ 70%), Medium (40–69%), Low (< 40%) based on predicted probability

---

## 📈 Key Findings

| Insight | Value |
|---|---|
| Overall churn rate | ~26.5% |
| Top churn contract | Month-to-month (≈ 43%) |
| Highest churn service | Fiber Optic internet |
| Riskiest payment method | Electronic check |
| Early churn window | Customers < 12 months tenure |
| Top feature (RF) | `tenure`, `MonthlyCharges`, `Contract` |

---

## 🛠️ Tech Stack

| Layer | Library |
|---|---|
| Data manipulation | `pandas`, `numpy` |
| Machine learning | `scikit-learn` |
| Visualisation | `plotly` |
| Dashboard | `dash` |
| Report generation | `python-docx` |

---

## 📄 License

MIT — free to use, modify, and distribute.
