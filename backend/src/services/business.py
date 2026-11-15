"""专栏续读风险：训练集拟合标准化，独立留出集评估。"""
import math
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["sessions_14d", "completion_pct", "days_inactive", "issues_read"]
LABELS = ["14日访问次数", "阅读完成率", "连续未读天数", "已读期数"]


def metadata():
    return {
        "name": "专栏续读风险试算", "short": "reader-risk",
        "tagline": "用行为窗口解释续读风险，再试算编辑关怀的覆盖边界。",
        "client": "纸岸知识出版社 · 6人内容运营组 · 320名匿名年度专栏读者",
        "workflow": "编辑每周合并阅读日志与到期续读结果，在表格中凭访问次数选择关怀对象。",
        "pains": ["各行为量纲不同，人工排序偏向高频用户", "直接使用到期后的数据会泄漏结果", "风险阈值缺少精确率与召回率依据"],
        "upstream": "到期前14日阅读行为快照 reader_window_202611.csv",
        "downstream": "主编据验证集覆盖人数安排内容回访实验，不自动触达读者",
        "entities": ["读者行为样本", "续读风险试验", "编辑复核简报"],
        "dataset_name": "纸岸专栏到期前14日匿名样本",
        "columns": [{"key": "reader_id", "label": "匿名读者", "type": "string"}] + [{"key": k, "label": l, "type": "number"} for k, l in zip(FEATURES, LABELS)] + [{"key": "renewed", "label": "实际续读(1/0)", "type": "number"}],
        "parameters": [{"key": "threshold", "label": "高风险概率阈值", "type": "number", "default": 0.5, "min": 0.1, "max": 0.9}, {"key": "regularization", "label": "模型C（越小正则越强）", "type": "number", "default": 1.0, "min": 0.01, "max": 10}],
        "workbench_title": "续读风险阈值试验", "action_label": "训练并复核覆盖范围", "unit": "位读者",
        "accent": "oklch(53% 0.12 30)", "style": "editorial-press",
        "seed_story": ["08:40 编辑导入 reader_window_202611.csv 的320条匿名样本", "08:45 检查14日访问、完成率、未读天数和已读期数", "09:00 以0.5风险阈值创建一次续读试验", "09:01 系统固定随机种子42，分层保留25%样本做验证", "09:05 编辑比较AUC、召回率与高风险人数", "09:10 将阈值改为0.7，复核误报减少及漏报增加", "09:20 下载验证明细交主编", "10:00 管理员设置周一08:30内部复核简报"],
        "method": "分层75/25留出；仅在训练集拟合StandardScaler和L2 logistic回归；目标为1-renewed；阈值只用于验证集决策。",
        "limitations": ["模拟读者行为，不能当作真实留存效果", "相关系数与模型系数不代表因果", "未包含时间外验证或干预效果评估"],
    }


def seed_records():
    rng = np.random.default_rng(1008)
    rows = []
    for i in range(320):
        sessions = int(rng.poisson(6))
        completion = float(np.clip(rng.normal(62, 21), 4, 99))
        inactive = int(rng.integers(0, 15))
        issues = int(rng.integers(1, 25))
        logit = -0.5 - 0.20 * sessions - 0.025 * (completion - 50) + 0.27 * inactive - 0.035 * issues
        risk = 1 / (1 + math.exp(-logit))
        rows.append({"reader_id": f"RD-{i+1:04}", "sessions_14d": sessions, "completion_pct": round(completion, 1), "days_inactive": inactive, "issues_read": issues, "renewed": int(rng.random() >= risk)})
    return rows


def analyze(records, params):
    try:
        threshold = float(params.get("threshold", 0.5))
        c_value = float(params.get("regularization", 1.0))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("风险阈值与模型C须为有效数值。") from exc
    if not 0.1 <= threshold <= 0.9 or not 0.01 <= c_value <= 10:
        raise ValueError("风险阈值须为0.1~0.9，模型C须为0.01~10。")
    if len(records) < 40:
        raise ValueError("至少需要40条完整样本，以保留独立验证集。")
    try:
        x = np.asarray([[float(row[k]) for k in FEATURES] for row in records])
        renewed = np.asarray([float(row["renewed"]) for row in records])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("行为字段与续读标签必须完整且为数值。") from exc
    if not np.isfinite(x).all() or not np.isin(renewed, [0, 1]).all() or (x < 0).any() or (x[:, 1] > 100).any():
        raise ValueError("行为值必须非负且有限，完成率0~100，续读标签只能为0/1。")
    y = 1 - renewed.astype(int)
    counts = np.bincount(y, minlength=2)
    if counts.min() < 8:
        raise ValueError("续读与未续读两类各至少8条样本。")
    indices = np.arange(len(records))
    train, valid = train_test_split(indices, test_size=0.25, stratify=y, random_state=42)
    model = make_pipeline(StandardScaler(), LogisticRegression(C=c_value, max_iter=1000, random_state=42))
    model.fit(x[train], y[train])
    probability = model.predict_proba(x[valid])[:, 1]
    prediction = (probability >= threshold).astype(int)
    auc = float(roc_auc_score(y[valid], probability))
    precision = float(precision_score(y[valid], prediction, zero_division=0))
    recall = float(recall_score(y[valid], prediction, zero_division=0))
    tn, fp, fn, tp = [int(v) for v in confusion_matrix(y[valid], prediction, labels=[0, 1]).ravel()]
    coefficients = model[-1].coef_[0]
    order = np.argsort(-probability)
    rows = [{"reader_id": str(records[int(valid[j])].get("reader_id", f"row-{int(valid[j])+1}")), "risk_pct": round(float(probability[j]) * 100, 2), "decision": "建议编辑复核" if prediction[j] else "维持观察", "actual": "未续读" if y[valid[j]] else "已续读"} for j in order]
    strongest = int(np.argmax(np.abs(coefficients)))
    return {
        "summary": f"训练{len(train)}条、独立验证{len(valid)}条；阈值{threshold:.2f}下有{int(prediction.sum())}位进入编辑复核。",
        "metrics": [{"label": "验证AUC", "value": round(auc, 4)}, {"label": "风险召回率", "value": round(recall * 100, 2), "unit": "%"}, {"label": "风险精确率", "value": round(precision * 100, 2), "unit": "%"}, {"label": "验证集高风险", "value": int(prediction.sum()), "unit": "人"}],
        "table": {"columns": [{"key": "reader_id", "label": "匿名读者"}, {"key": "risk_pct", "label": "风险概率(%)"}, {"key": "decision", "label": "阈值决策"}, {"key": "actual", "label": "留出集实际结果"}], "rows": rows},
        "chart": {"type": "bar", "labels": LABELS, "series": [{"name": "标准化log-odds系数", "values": [round(float(v), 4) for v in coefficients]}]},
        "findings": [f"验证混淆矩阵：命中未续读{tp}、误报{fp}、漏报{fn}、正确排除{tn}。", f"绝对系数最大的特征为{LABELS[strongest]}（{float(coefficients[strongest]):.3f}）；正值意味着更高未续读风险。", f"验证准确率{accuracy_score(y[valid], prediction)*100:.1f}%；阈值变更影响覆盖边界，不改变AUC。"],
        "method": metadata()["method"], "warnings": ["风险排序供编辑复核使用，不能据此断言某项行为导致未续读。"],
    }
