"""
医学用語辞書
日本語の医学用語を英語にマッピング
"""

# 薬物名
DRUG_NAMES = {
    'セマグルチド': 'semaglutide',
    'メトホルミン': 'metformin',
    'メトフォルミン': 'metformin',
    'インスリン': 'insulin',
    'リラグルチド': 'liraglutide',
    'デュラグルチド': 'dulaglutide',
    'エキセナチド': 'exenatide',
    'チルゼパチド': 'tirzepatide',
    'エンパグリフロジン': 'empagliflozin',
    'ダパグリフロジン': 'dapagliflozin',
    'カナグリフロジン': 'canagliflozin',
    'アスピリン': 'aspirin',
    'スタチン': 'statin',
    'アトルバスタチン': 'atorvastatin',
    'ロスバスタチン': 'rosuvastatin',
    'シンバスタチン': 'simvastatin',
    'ワルファリン': 'warfarin',
    'ヘパリン': 'heparin',
    'クロピドグレル': 'clopidogrel',
    'オメプラゾール': 'omeprazole',
    'ランソプラゾール': 'lansoprazole',
    'アモキシシリン': 'amoxicillin',
    'ペニシリン': 'penicillin',
    'レボフロキサシン': 'levofloxacin',
    'アジスロマイシン': 'azithromycin',
    'プレドニゾロン': 'prednisolone',
    'デキサメタゾン': 'dexamethasone',
    'ヒドロコルチゾン': 'hydrocortisone',
    'アムロジピン': 'amlodipine',
    'ニフェジピン': 'nifedipine',
    'エナラプリル': 'enalapril',
    'ロサルタン': 'losartan',
    'バルサルタン': 'valsartan',
    'メトプロロール': 'metoprolol',
    'カルベジロール': 'carvedilol',
    'フロセミド': 'furosemide',
    'スピロノラクトン': 'spironolactone',
    'レボチロキシン': 'levothyroxine',
    'ガバペンチン': 'gabapentin',
    'プレガバリン': 'pregabalin',
}

# 疾患名
DISEASE_NAMES = {
    '糖尿病': 'diabetes',
    '2型糖尿病': 'type 2 diabetes',
    '1型糖尿病': 'type 1 diabetes',
    '高血圧': 'hypertension',
    '低血圧': 'hypotension',
    'がん': 'cancer',
    '癌': 'cancer',
    '肺がん': 'lung cancer',
    '大腸がん': 'colorectal cancer',
    '乳がん': 'breast cancer',
    '胃がん': 'gastric cancer',
    '肝がん': 'liver cancer',
    '前立腺がん': 'prostate cancer',
    '心臓病': 'heart disease',
    '心筋梗塞': 'myocardial infarction',
    '狭心症': 'angina',
    '心不全': 'heart failure',
    '不整脈': 'arrhythmia',
    '脳卒中': 'stroke',
    '脳梗塞': 'cerebral infarction',
    '脳出血': 'cerebral hemorrhage',
    '肺炎': 'pneumonia',
    '気管支炎': 'bronchitis',
    '喘息': 'asthma',
    '慢性閉塞性肺疾患': 'COPD',
    '腎不全': 'renal failure',
    '腎臓病': 'kidney disease',
    '肝炎': 'hepatitis',
    '肝硬変': 'cirrhosis',
    '脂肪肝': 'fatty liver',
    '関節リウマチ': 'rheumatoid arthritis',
    '変形性関節症': 'osteoarthritis',
    '骨粗鬆症': 'osteoporosis',
    'アルツハイマー病': 'Alzheimer disease',
    '認知症': 'dementia',
    'パーキンソン病': 'Parkinson disease',
    'うつ病': 'depression',
    '統合失調症': 'schizophrenia',
    '不安症': 'anxiety disorder',
    '甲状腺機能亢進症': 'hyperthyroidism',
    '甲状腺機能低下症': 'hypothyroidism',
    '肥満': 'obesity',
    'メタボリックシンドローム': 'metabolic syndrome',
    '動脈硬化': 'atherosclerosis',
    '高脂血症': 'hyperlipidemia',
    '高コレステロール血症': 'hypercholesterolemia',
    '痛風': 'gout',
    '貧血': 'anemia',
}

# 症状・所見
SYMPTOMS = {
    '体重減少': 'weight loss',
    '体重減少効果': 'weight loss',  # 複合語を追加
    '体重増加': 'weight gain',
    '減量': 'weight loss',
    '減量効果': 'weight loss',  # 複合語を追加
    '発熱': 'fever',
    '頭痛': 'headache',
    'めまい': 'dizziness',
    '吐き気': 'nausea',
    '嘔吐': 'vomiting',
    '下痢': 'diarrhea',
    '便秘': 'constipation',
    '腹痛': 'abdominal pain',
    '胸痛': 'chest pain',
    '息切れ': 'dyspnea',
    '呼吸困難': 'dyspnea',
    '咳': 'cough',
    '痰': 'sputum',
    '倦怠感': 'fatigue',
    '疲労': 'fatigue',
    '浮腫': 'edema',
    'むくみ': 'edema',
    '発疹': 'rash',
    'かゆみ': 'itching',
    '痛み': 'pain',
    '疼痛': 'pain',
    '不眠': 'insomnia',
    '食欲不振': 'anorexia',
    '血糖値': 'blood glucose',
    '血圧': 'blood pressure',
    'コレステロール': 'cholesterol',
    'ヘモグロビン': 'hemoglobin',
    'HbA1c': 'HbA1c',
}

# 治療関連
TREATMENT_TERMS = {
    '治療': 'treatment',
    '治療法': 'therapy',
    '副作用': 'side effects',
    '有害事象': 'adverse events',
    '効果': 'efficacy',
    '有効性': 'efficacy',
    '安全性': 'safety',
    '投与': 'administration',
    '服用': 'administration',
    '経口': 'oral',
    '注射': 'injection OR injectable OR subcutaneous',
    '皮下注射': 'subcutaneous injection',
    '筋肉注射': 'intramuscular injection',
    '静脈注射': 'intravenous injection',
    '点滴': 'intravenous infusion',
    '手術': 'surgery',
    '外科手術': 'surgical operation',
    '化学療法': 'chemotherapy',
    '放射線療法': 'radiation therapy',
    '免疫療法': 'immunotherapy',
    'リハビリテーション': 'rehabilitation',
    '予防': 'prevention',
    '診断': 'diagnosis',
    '検査': 'test OR examination',
    '臨床試験': 'clinical trial',
    'ランダム化比較試験': 'randomized controlled trial',
    'プラセボ': 'placebo',
    '用量': 'dose',
    '用法': 'dosage',
    '投与量': 'dose',
    '併用': 'combination',
    '単独療法': 'monotherapy',
    '併用療法': 'combination therapy',
    '長期': 'long-term',
    '短期': 'short-term',
    '慢性': 'chronic',
    '急性': 'acute',
}

# 比較・疑問詞
COMPARISON_TERMS = {
    # 比較関連の用語は検索を狭めすぎるため、削除または弱める
    # '違い': 'difference',  # コメントアウト - 検索結果を狭めすぎる
    # '比較': 'comparison',  # コメントアウト - 検索結果を狭めすぎる
    'より': 'better',
    '優れる': 'superior',
    '劣る': 'inferior',
    '同等': 'equivalent',
    '有意差': 'significant difference',
    'エビデンス': 'evidence',
    '研究': 'study',
    '論文': 'article',
    'メタアナリシス': 'meta-analysis',
    'システマティックレビュー': 'systematic review',
    'ガイドライン': 'guideline',
    '推奨': 'recommendation',
}

def get_medical_term(japanese_word: str) -> str:
    """
    日本語医学用語を英語に変換

    Args:
        japanese_word: 日本語の医学用語

    Returns:
        英語の医学用語（見つからない場合はNone）
    """
    # 全辞書を検索
    for dict_name in [DRUG_NAMES, DISEASE_NAMES, SYMPTOMS,
                      TREATMENT_TERMS, COMPARISON_TERMS]:
        if japanese_word in dict_name:
            return dict_name[japanese_word]
    return None


def get_all_terms() -> dict:
    """
    全ての医学用語辞書を統合して返す

    Returns:
        統合された辞書
    """
    all_terms = {}
    all_terms.update(DRUG_NAMES)
    all_terms.update(DISEASE_NAMES)
    all_terms.update(SYMPTOMS)
    all_terms.update(TREATMENT_TERMS)
    all_terms.update(COMPARISON_TERMS)
    return all_terms
