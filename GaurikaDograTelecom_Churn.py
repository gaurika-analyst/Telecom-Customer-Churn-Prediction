# =============================================================================
#  Telecom Customer Churn Prediction & Business Analytics
#  Single-file application: ML backend + Interactive Dash frontend
# =============================================================================

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from pathlib import Path

# ── Scikit-learn ──────────────────────────────────────────────────────────────
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report
)
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

# ── Dash / Plotly ─────────────────────────────────────────────────────────────
import dash
from dash import dcc, html, dash_table, Input, Output, callback
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# =============================================================================
#  1. DATA LOADING & PREPROCESSING
# =============================================================================

DATA_FILE = "telecom_churn.csv"

def load_and_preprocess(path: str):
    df = pd.read_csv(path)

    # Fix TotalCharges – spaces → NaN, then coerce
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"].str.strip(), errors="coerce")
    df["TotalCharges"].fillna(df["TotalCharges"].median(), inplace=True)

    # Binary target
    df["ChurnBinary"] = (df["Churn"] == "Yes").astype(int)

    # Ordinal Contract encoding for analysis
    contract_order = {"Month-to-month": 0, "One year": 1, "Two year": 2}
    df["ContractCode"] = df["Contract"].map(contract_order)

    # Revenue at risk = monthly charges of churned / total monthly charges
    df["RevenueAtRisk"] = df["MonthlyCharges"] * df["ChurnBinary"]

    return df


df_raw = load_and_preprocess(DATA_FILE)

# =============================================================================
#  2. FEATURE ENGINEERING FOR MODEL
# =============================================================================

def build_features(df: pd.DataFrame):
    drop_cols = ["customerID", "Churn", "ChurnBinary", "RevenueAtRisk",
                 "ContractCode", "TenureBucket", "RiskSegment",
                 "ChurnProb", "ChurnPredicted"]
    existing_drop = [c for c in drop_cols if c in df.columns]
    X = df.drop(columns=existing_drop)
    y = df["ChurnBinary"]

    # Encode categoricals
    le = LabelEncoder()
    cat_cols = X.select_dtypes(include="object").columns.tolist()
    X_enc = X.copy()
    for col in cat_cols:
        X_enc[col] = le.fit_transform(X_enc[col].astype(str))

    # Fill any remaining NaN (e.g. TotalCharges edge cases)
    X_enc = X_enc.fillna(X_enc.median(numeric_only=True))

    return X_enc, y, cat_cols


X, y, cat_cols = build_features(df_raw)

# =============================================================================
#  3. MODEL TRAINING & EVALUATION
# =============================================================================

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s  = scaler.transform(X_test)

models = {
    "Logistic Regression": LogisticRegression(max_iter=1000, random_state=42),
    "Random Forest":       RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1),
    "Gradient Boosting":   GradientBoostingClassifier(n_estimators=200, random_state=42),
}

results = {}
best_model_name = None
best_f1 = 0.0

for name, model in models.items():
    use_scaled = (name == "Logistic Regression")
    Xtr = X_train_s if use_scaled else X_train
    Xte = X_test_s  if use_scaled else X_test

    model.fit(Xtr, y_train)
    preds  = model.predict(Xte)
    probas = model.predict_proba(Xte)[:, 1]

    metrics = {
        "Accuracy":  round(accuracy_score(y_test, preds) * 100, 2),
        "Precision": round(precision_score(y_test, preds) * 100, 2),
        "Recall":    round(recall_score(y_test, preds) * 100, 2),
        "F1 Score":  round(f1_score(y_test, preds) * 100, 2),
        "ROC-AUC":   round(roc_auc_score(y_test, probas) * 100, 2),
        "Confusion Matrix": confusion_matrix(y_test, preds).tolist(),
    }
    results[name] = metrics

    if metrics["F1 Score"] > best_f1:
        best_f1 = metrics["F1 Score"]
        best_model_name = name

# Best model predictions on full dataset
best_clf = models[best_model_name]
use_scaled_best = (best_model_name == "Logistic Regression")
X_full = scaler.transform(X) if use_scaled_best else X

df_raw["ChurnProb"]     = best_clf.predict_proba(X_full)[:, 1]
df_raw["ChurnPredicted"] = best_clf.predict(X_full)

# Risk segments
def risk_segment(p):
    if p >= 0.70: return "High Risk"
    if p >= 0.40: return "Medium Risk"
    return "Low Risk"

df_raw["RiskSegment"] = df_raw["ChurnProb"].apply(risk_segment)

# Feature importances (Random Forest)
rf = models["Random Forest"]
feat_imp = pd.DataFrame({
    "Feature": X.columns,
    "Importance": rf.feature_importances_
}).sort_values("Importance", ascending=False).head(10)

# =============================================================================
#  4. EXECUTIVE KPI CALCULATIONS
# =============================================================================

total_customers  = len(df_raw)
churned          = int(df_raw["ChurnBinary"].sum())
churn_rate       = round(churned / total_customers * 100, 2)
revenue_at_risk  = round(df_raw[df_raw["ChurnBinary"] == 1]["MonthlyCharges"].sum(), 2)
avg_monthly_chg  = round(df_raw["MonthlyCharges"].mean(), 2)
avg_tenure       = round(df_raw["tenure"].mean(), 1)
high_risk_count  = int((df_raw["RiskSegment"] == "High Risk").sum())
retention_oppty  = round(df_raw[df_raw["RiskSegment"] == "High Risk"]["MonthlyCharges"].sum(), 2)

# Contract mix
contract_churn = df_raw.groupby("Contract")["ChurnBinary"].mean().reset_index()
contract_churn.columns = ["Contract", "ChurnRate"]
contract_churn["ChurnRate"] = (contract_churn["ChurnRate"] * 100).round(2)

# Tenure buckets
bins   = [0, 12, 24, 48, 72]
labels = ["0–12 mo", "13–24 mo", "25–48 mo", "49–72 mo"]
df_raw["TenureBucket"] = pd.cut(df_raw["tenure"], bins=bins, labels=labels, right=True)
tenure_churn = df_raw.groupby("TenureBucket", observed=True)["ChurnBinary"].mean().reset_index()
tenure_churn.columns = ["TenureBucket", "ChurnRate"]
tenure_churn["ChurnRate"] = (tenure_churn["ChurnRate"] * 100).round(2)

# Monthly charges distribution
df_churn_yes = df_raw[df_raw["Churn"] == "Yes"]["MonthlyCharges"]
df_churn_no  = df_raw[df_raw["Churn"] == "No"]["MonthlyCharges"]

# Internet service churn
internet_churn = df_raw.groupby("InternetService")["ChurnBinary"].mean().reset_index()
internet_churn.columns = ["InternetService", "ChurnRate"]
internet_churn["ChurnRate"] = (internet_churn["ChurnRate"] * 100).round(2)

# Payment method churn
payment_churn = df_raw.groupby("PaymentMethod")["ChurnBinary"].mean().reset_index()
payment_churn.columns = ["PaymentMethod", "ChurnRate"]
payment_churn["ChurnRate"] = (payment_churn["ChurnRate"] * 100).round(2)

# High-risk customers table
high_risk_df = df_raw[df_raw["RiskSegment"] == "High Risk"][
    ["customerID", "Contract", "tenure", "MonthlyCharges",
     "InternetService", "PaymentMethod", "ChurnProb"]
].copy()
high_risk_df["ChurnProb"] = (high_risk_df["ChurnProb"] * 100).round(1)
high_risk_df = high_risk_df.sort_values("ChurnProb", ascending=False).head(50)
high_risk_df.rename(columns={
    "customerID": "Customer ID",
    "Contract": "Contract",
    "tenure": "Tenure (mo)",
    "MonthlyCharges": "Monthly Charges ($)",
    "InternetService": "Internet",
    "PaymentMethod": "Payment",
    "ChurnProb": "Churn Prob (%)"
}, inplace=True)

# Model comparison table
model_comparison = []
for name, m in results.items():
    model_comparison.append({
        "Model": name,
        "Accuracy (%)": m["Accuracy"],
        "Precision (%)": m["Precision"],
        "Recall (%)": m["Recall"],
        "F1 Score (%)": m["F1 Score"],
        "ROC-AUC (%)": m["ROC-AUC"],
    })
model_df = pd.DataFrame(model_comparison)

# =============================================================================
#  5. COLOUR PALETTE & STYLE CONSTANTS
# =============================================================================

COLORS = {
    "bg":        "#0f172a",
    "card":      "#1e293b",
    "border":    "#334155",
    "accent":    "#38bdf8",
    "accent2":   "#818cf8",
    "danger":    "#f87171",
    "warn":      "#fb923c",
    "success":   "#34d399",
    "text":      "#f1f5f9",
    "muted":     "#94a3b8",
    "chart_bg":  "#1e293b",
}

FONT = "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"

PLOT_LAYOUT = dict(
    paper_bgcolor=COLORS["chart_bg"],
    plot_bgcolor=COLORS["chart_bg"],
    font=dict(color=COLORS["text"], family=FONT, size=12),
    margin=dict(l=40, r=20, t=40, b=40),
    colorway=[COLORS["accent"], COLORS["accent2"], COLORS["success"],
              COLORS["warn"], COLORS["danger"]],
)

def card(children, style_extra=None):
    style = {
        "background": COLORS["card"],
        "border": f'1px solid {COLORS["border"]}',
        "borderRadius": "12px",
        "padding": "20px",
        "marginBottom": "16px",
    }
    if style_extra:
        style.update(style_extra)
    return html.Div(children, style=style)

def kpi_card(label, value, sub="", color=None):
    return html.Div([
        html.P(label, style={"margin": 0, "fontSize": "12px",
                             "color": COLORS["muted"], "textTransform": "uppercase",
                             "letterSpacing": "0.08em"}),
        html.H2(value, style={"margin": "4px 0 2px", "fontSize": "28px",
                               "color": color or COLORS["text"], "fontWeight": 700}),
        html.P(sub, style={"margin": 0, "fontSize": "11px", "color": COLORS["muted"]}),
    ], style={
        "background": COLORS["card"],
        "border": f'1px solid {COLORS["border"]}',
        "borderRadius": "12px",
        "padding": "20px 24px",
        "flex": "1",
        "minWidth": "160px",
    })

# =============================================================================
#  6. DASH APPLICATION LAYOUT
# =============================================================================

app = dash.Dash(
    __name__,
    title="Telecom Churn Analytics",
    suppress_callback_exceptions=True,
)
server = app.server   # expose for WSGI deployment

# ── Navigation tabs ──────────────────────────────────────────────────────────
TAB_STYLE = {
    "background": COLORS["bg"],
    "color": COLORS["muted"],
    "border": "none",
    "borderBottom": f'2px solid transparent',
    "padding": "12px 24px",
    "fontSize": "13px",
    "fontFamily": FONT,
    "cursor": "pointer",
}
TAB_SELECTED = {
    **TAB_STYLE,
    "color": COLORS["accent"],
    "borderBottom": f'2px solid {COLORS["accent"]}',
    "background": COLORS["bg"],
}

app.layout = html.Div(style={
    "background": COLORS["bg"],
    "minHeight": "100vh",
    "fontFamily": FONT,
    "color": COLORS["text"],
}, children=[

    # ── Header ───────────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            html.H1("📡 Telecom Churn Analytics",
                    style={"margin": 0, "fontSize": "22px", "fontWeight": 700,
                           "color": COLORS["text"]}),
            html.P(f"Best model: {best_model_name}  ·  "
                   f"F1: {results[best_model_name]['F1 Score']}%  ·  "
                   f"ROC-AUC: {results[best_model_name]['ROC-AUC']}%  ·  "
                   f"Dataset: {total_customers:,} customers",
                   style={"margin": "4px 0 0", "fontSize": "12px",
                          "color": COLORS["muted"]}),
        ]),
    ], style={"background": COLORS["card"],
              "borderBottom": f'1px solid {COLORS["border"]}',
              "padding": "16px 32px"}),

    # ── Tabs ─────────────────────────────────────────────────────────────────
    dcc.Tabs(id="tabs", value="tab-kpi", style={"background": COLORS["bg"]},
             children=[
        dcc.Tab(label="🏢 Executive KPIs",        value="tab-kpi",
                style=TAB_STYLE, selected_style=TAB_SELECTED),
        dcc.Tab(label="📊 Churn Risk Drivers",    value="tab-drivers",
                style=TAB_STYLE, selected_style=TAB_SELECTED),
        dcc.Tab(label="🤖 Model Performance",     value="tab-model",
                style=TAB_STYLE, selected_style=TAB_SELECTED),
        dcc.Tab(label="🎯 Retention Strategies",  value="tab-retention",
                style=TAB_STYLE, selected_style=TAB_SELECTED),
    ]),

    html.Div(id="tab-content", style={"padding": "24px 32px"}),
])

# =============================================================================
#  7. TAB CONTENT CALLBACKS
# =============================================================================

@app.callback(Output("tab-content", "children"), Input("tabs", "value"))
def render_tab(tab):

    # ── TAB 1 · Executive KPIs ────────────────────────────────────────────
    if tab == "tab-kpi":

        # Churn donut
        donut = go.Figure(go.Pie(
            labels=["Active", "Churned"],
            values=[total_customers - churned, churned],
            hole=0.65,
            marker_colors=[COLORS["success"], COLORS["danger"]],
            textfont_size=13,
        ))
        donut.update_layout(**PLOT_LAYOUT,
                            title="Overall Churn Split",
                            showlegend=True,
                            legend=dict(orientation="h", y=-0.1))
        donut.add_annotation(text=f"{churn_rate}%<br>Churn",
                             x=0.5, y=0.5, font_size=20,
                             font_color=COLORS["danger"],
                             showarrow=False)

        # Risk segment pie
        seg_counts = df_raw["RiskSegment"].value_counts().reset_index()
        seg_counts.columns = ["Segment", "Count"]
        seg_pie = px.pie(seg_counts, names="Segment", values="Count",
                         title="Predicted Risk Segments",
                         color="Segment",
                         color_discrete_map={
                             "High Risk":   COLORS["danger"],
                             "Medium Risk": COLORS["warn"],
                             "Low Risk":    COLORS["success"],
                         })
        seg_pie.update_traces(hole=0.5, textfont_size=12)
        seg_pie.update_layout(**PLOT_LAYOUT)

        # Monthly charges by churn
        mc_fig = go.Figure()
        mc_fig.add_trace(go.Histogram(x=df_churn_no,  name="Not Churned",
                                      marker_color=COLORS["success"], opacity=0.7,
                                      xbins=dict(size=5)))
        mc_fig.add_trace(go.Histogram(x=df_churn_yes, name="Churned",
                                      marker_color=COLORS["danger"], opacity=0.7,
                                      xbins=dict(size=5)))
        mc_fig.update_layout(**PLOT_LAYOUT, barmode="overlay",
                             title="Monthly Charges Distribution by Churn",
                             xaxis_title="Monthly Charges ($)",
                             yaxis_title="Count")

        return html.Div([
            # KPI row
            html.Div([
                kpi_card("Total Customers", f"{total_customers:,}", "full dataset"),
                kpi_card("Churned",          f"{churned:,}", f"{churn_rate}% churn rate",
                         color=COLORS["danger"]),
                kpi_card("Revenue at Risk",  f"${revenue_at_risk:,.0f}",
                         "monthly from churned", color=COLORS["warn"]),
                kpi_card("Avg Monthly Charge", f"${avg_monthly_chg}",
                         "per customer"),
                kpi_card("Avg Tenure",       f"{avg_tenure} mo",
                         "across all customers"),
                kpi_card("High-Risk (≥70%)", f"{high_risk_count:,}",
                         f"${retention_oppty:,.0f}/mo opportunity",
                         color=COLORS["danger"]),
            ], style={"display": "flex", "gap": "12px",
                      "flexWrap": "wrap", "marginBottom": "16px"}),

            # Charts row
            html.Div([
                card([dcc.Graph(figure=donut, config={"displayModeBar": False})],
                     {"flex": "1", "minWidth": "300px"}),
                card([dcc.Graph(figure=seg_pie, config={"displayModeBar": False})],
                     {"flex": "1", "minWidth": "300px"}),
                card([dcc.Graph(figure=mc_fig, config={"displayModeBar": False})],
                     {"flex": "2", "minWidth": "400px"}),
            ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),
        ])

    # ── TAB 2 · Churn Risk Drivers ────────────────────────────────────────
    elif tab == "tab-drivers":

        # Contract type churn
        contract_fig = px.bar(
            contract_churn, x="Contract", y="ChurnRate",
            title="Churn Rate by Contract Type",
            color="ChurnRate",
            color_continuous_scale=["#34d399", "#fb923c", "#f87171"],
            text="ChurnRate",
        )
        contract_fig.update_traces(texttemplate="%{text}%", textposition="outside")
        contract_fig.update_layout(**PLOT_LAYOUT, yaxis_title="Churn Rate (%)",
                                   coloraxis_showscale=False)

        # Tenure bucket churn
        tenure_fig = px.bar(
            tenure_churn, x="TenureBucket", y="ChurnRate",
            title="Churn Rate by Customer Tenure",
            color="ChurnRate",
            color_continuous_scale=["#34d399", "#fb923c", "#f87171"],
            text="ChurnRate",
        )
        tenure_fig.update_traces(texttemplate="%{text}%", textposition="outside")
        tenure_fig.update_layout(**PLOT_LAYOUT, yaxis_title="Churn Rate (%)",
                                 coloraxis_showscale=False)

        # Feature importance
        fi_fig = px.bar(
            feat_imp.sort_values("Importance"), x="Importance", y="Feature",
            orientation="h", title="Top 10 Feature Importances (Random Forest)",
            color="Importance",
            color_continuous_scale=["#818cf8", "#38bdf8"],
        )
        fi_fig.update_layout(**PLOT_LAYOUT, xaxis_title="Importance Score",
                             coloraxis_showscale=False)

        # Internet service churn
        inet_fig = px.bar(
            internet_churn, x="InternetService", y="ChurnRate",
            title="Churn Rate by Internet Service",
            color="ChurnRate",
            color_continuous_scale=["#34d399", "#fb923c", "#f87171"],
            text="ChurnRate",
        )
        inet_fig.update_traces(texttemplate="%{text}%", textposition="outside")
        inet_fig.update_layout(**PLOT_LAYOUT, yaxis_title="Churn Rate (%)",
                               coloraxis_showscale=False)

        # Payment method churn
        pay_fig = px.bar(
            payment_churn, x="PaymentMethod", y="ChurnRate",
            title="Churn Rate by Payment Method",
            color="ChurnRate",
            color_continuous_scale=["#34d399", "#fb923c", "#f87171"],
            text="ChurnRate",
        )
        pay_fig.update_traces(texttemplate="%{text}%", textposition="outside")
        pay_fig.update_layout(**PLOT_LAYOUT, yaxis_title="Churn Rate (%)",
                               coloraxis_showscale=False,
                               xaxis_tickangle=-25)

        # Churn probability scatter – tenure vs monthly charges
        scatter_fig = px.scatter(
            df_raw.sample(min(2000, len(df_raw)), random_state=42),
            x="tenure", y="MonthlyCharges",
            color="RiskSegment",
            color_discrete_map={
                "High Risk":   COLORS["danger"],
                "Medium Risk": COLORS["warn"],
                "Low Risk":    COLORS["success"],
            },
            title="Churn Probability: Tenure vs Monthly Charges",
            opacity=0.65, size_max=6,
        )
        scatter_fig.update_layout(**PLOT_LAYOUT,
                                  xaxis_title="Tenure (months)",
                                  yaxis_title="Monthly Charges ($)")

        return html.Div([
            html.Div([
                card([dcc.Graph(figure=contract_fig, config={"displayModeBar": False})],
                     {"flex": "1", "minWidth": "300px"}),
                card([dcc.Graph(figure=tenure_fig, config={"displayModeBar": False})],
                     {"flex": "1", "minWidth": "300px"}),
            ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),

            html.Div([
                card([dcc.Graph(figure=fi_fig, config={"displayModeBar": False})],
                     {"flex": "1", "minWidth": "300px"}),
                card([dcc.Graph(figure=scatter_fig, config={"displayModeBar": False})],
                     {"flex": "2", "minWidth": "400px"}),
            ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),

            html.Div([
                card([dcc.Graph(figure=inet_fig, config={"displayModeBar": False})],
                     {"flex": "1", "minWidth": "300px"}),
                card([dcc.Graph(figure=pay_fig, config={"displayModeBar": False})],
                     {"flex": "1", "minWidth": "300px"}),
            ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),
        ])

    # ── TAB 3 · Model Performance ─────────────────────────────────────────
    elif tab == "tab-model":

        # Model comparison bar chart
        metric_cols = ["Accuracy (%)", "Precision (%)", "Recall (%)",
                       "F1 Score (%)", "ROC-AUC (%)"]
        model_fig = go.Figure()
        for col in metric_cols:
            model_fig.add_trace(go.Bar(
                name=col.replace(" (%)", ""),
                x=model_df["Model"],
                y=model_df[col],
                text=model_df[col].apply(lambda v: f"{v}%"),
                textposition="outside",
            ))
        model_fig.update_layout(**PLOT_LAYOUT, barmode="group",
                               title="Model Performance Comparison",
                               yaxis=dict(range=[0, 110]),
                               yaxis_title="Score (%)")

        # Confusion matrices
        cm_figs = []
        for name, m in results.items():
            cm = np.array(m["Confusion Matrix"])
            cm_fig = px.imshow(
                cm,
                labels=dict(x="Predicted", y="Actual", color="Count"),
                x=["Not Churned", "Churned"],
                y=["Not Churned", "Churned"],
                color_continuous_scale=["#1e293b", "#38bdf8"],
                title=f"Confusion Matrix – {name}",
                text_auto=True,
            )
            cm_fig.update_layout(**PLOT_LAYOUT)
            cm_figs.append(
                card([dcc.Graph(figure=cm_fig, config={"displayModeBar": False})],
                     {"flex": "1", "minWidth": "260px"})
            )

        # Metrics table
        table = dash_table.DataTable(
            data=model_df.to_dict("records"),
            columns=[{"name": c, "id": c} for c in model_df.columns],
            style_table={"overflowX": "auto"},
            style_header={
                "backgroundColor": COLORS["bg"],
                "color": COLORS["accent"],
                "fontWeight": "600",
                "border": f'1px solid {COLORS["border"]}',
                "fontSize": "12px",
            },
            style_cell={
                "backgroundColor": COLORS["card"],
                "color": COLORS["text"],
                "border": f'1px solid {COLORS["border"]}',
                "padding": "10px 14px",
                "fontFamily": FONT,
                "fontSize": "13px",
            },
            style_data_conditional=[
                {"if": {"filter_query": f'{{Model}} = "{best_model_name}"'},
                 "backgroundColor": "#0c2340",
                 "color": COLORS["accent"],
                 "fontWeight": "bold"},
            ],
        )

        return html.Div([
            card([dcc.Graph(figure=model_fig, config={"displayModeBar": False})]),
            card([
                html.H3(f"📋 Metrics Summary  ·  Best: {best_model_name}",
                        style={"margin": "0 0 12px", "fontSize": "14px",
                               "color": COLORS["accent"]}),
                table,
            ]),
            html.Div(cm_figs,
                     style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),
        ])

    # ── TAB 4 · Retention Strategies ──────────────────────────────────────
    elif tab == "tab-retention":

        strategy_cards = [
            ("🔴 High-Risk · Month-to-Month Customers",
             COLORS["danger"],
             [
                 "Offer personalised 1-year or 2-year contract upgrades with a 15–20% monthly discount.",
                 "Trigger proactive outreach (call/email) within 48 h of detecting high churn probability.",
                 "Bundle free premium add-ons (StreamingTV, Online Security) for first 6 months to increase stickiness.",
             ]),
            ("🟠 High-Risk · Fiber Optic Subscribers",
             COLORS["warn"],
             [
                 "Fiber optic customers churn at 2–3× the rate of DSL users — prioritise service quality SLAs.",
                 "Run loyalty rewards programme: credit back $10/mo for each consecutive on-time payment.",
                 "Offer speed upgrade promotions: make higher-tier plans financially attractive vs. switching.",
             ]),
            ("🟡 Medium-Risk · Electronic-Check Payers",
             "#facc15",
             [
                 "Electronic check users show the highest churn propensity — migrate them to auto-pay.",
                 "Provide a $5/mo AutoPay discount to incentivise credit-card or bank-transfer setup.",
                 "Send billing reminders and introduce a self-service portal to reduce payment friction.",
             ]),
            ("🟢 Early Tenure Customers (0–12 Months)",
             COLORS["success"],
             [
                 "First-year onboarding is critical — deploy a dedicated Customer Success team for new users.",
                 "Send educational content (feature tips, tutorials) in months 2–6 to demonstrate value.",
                 "Offer a '30-day satisfaction guarantee' to reduce early cancellation anxiety.",
             ]),
            ("📈 Cross-Sell to Reduce Churn",
             COLORS["accent"],
             [
                 "Customers with Online Security & Tech Support add-ons churn at significantly lower rates.",
                 "Target single-service customers with bundled upgrade offers (phone + internet + streaming).",
                 "Use the churn probability score to rank marketing spend — focus on 40–70% probability band.",
             ]),
        ]

        strat_divs = []
        for title_s, color, points in strategy_cards:
            strat_divs.append(html.Div([
                html.H4(title_s, style={"margin": "0 0 10px",
                                        "color": color, "fontSize": "14px"}),
                html.Ul([html.Li(p, style={"marginBottom": "6px",
                                            "color": COLORS["muted"],
                                            "fontSize": "13px",
                                            "lineHeight": "1.6"})
                         for p in points]),
            ], style={
                "background": COLORS["card"],
                "border": f'1px solid {color}',
                "borderLeft": f'4px solid {color}',
                "borderRadius": "10px",
                "padding": "16px 20px",
                "marginBottom": "12px",
            }))

        # High-risk customer table
        hr_table = dash_table.DataTable(
            data=high_risk_df.to_dict("records"),
            columns=[{"name": c, "id": c} for c in high_risk_df.columns],
            page_size=10,
            sort_action="native",
            filter_action="native",
            style_table={"overflowX": "auto"},
            style_header={
                "backgroundColor": COLORS["bg"],
                "color": COLORS["accent"],
                "fontWeight": "600",
                "border": f'1px solid {COLORS["border"]}',
                "fontSize": "12px",
            },
            style_cell={
                "backgroundColor": COLORS["card"],
                "color": COLORS["text"],
                "border": f'1px solid {COLORS["border"]}',
                "padding": "9px 12px",
                "fontFamily": FONT,
                "fontSize": "12px",
            },
            style_data_conditional=[
                {"if": {"filter_query": "{Churn Prob (%)} >= 85"},
                 "color": COLORS["danger"], "fontWeight": "bold"},
                {"if": {"filter_query": "{Churn Prob (%)} >= 70 && {Churn Prob (%)} < 85"},
                 "color": COLORS["warn"]},
            ],
        )

        return html.Div([
            html.Div([
                html.Div(strat_divs, style={"flex": "1", "minWidth": "320px"}),
                html.Div([
                    card([
                        html.H3("🎯 Top 50 High-Risk Customers",
                                style={"margin": "0 0 12px", "fontSize": "14px",
                                       "color": COLORS["accent"]}),
                        html.P(f"Showing customers with predicted churn probability ≥ 70%. "
                               f"Total high-risk pool: {high_risk_count:,} customers  ·  "
                               f"${retention_oppty:,.0f}/mo revenue at stake.",
                               style={"margin": "0 0 14px", "fontSize": "12px",
                                      "color": COLORS["muted"]}),
                        hr_table,
                    ])
                ], style={"flex": "2", "minWidth": "400px"}),
            ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),
        ])


# =============================================================================
#  8. ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Telecom Churn Prediction & Business Analytics")
    print("=" * 60)
    print(f"  Dataset     : {DATA_FILE}  ({total_customers:,} customers)")
    print(f"  Churn Rate  : {churn_rate}%  ({churned:,} churned)")
    print(f"  Best Model  : {best_model_name}")
    print(f"  F1 Score    : {results[best_model_name]['F1 Score']}%")
    print(f"  ROC-AUC     : {results[best_model_name]['ROC-AUC']}%")
    print(f"  High-Risk   : {high_risk_count:,} customers")
    print(f"  Revenue Risk: ${revenue_at_risk:,.0f}/mo")
    print("=" * 60)
    print("  Dashboard → http://127.0.0.1:8050")
    print("=" * 60)
    app.run(debug=False, host="127.0.0.1", port=8050)
