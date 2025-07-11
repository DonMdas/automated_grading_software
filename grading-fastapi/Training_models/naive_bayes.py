import json
import pandas as pd
import numpy as np
import joblib
import os
from sklearn.naive_bayes import GaussianNB
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# -----------------------------
# Configs
# -----------------------------
FEATURE_COLUMNS = ['tf_idf_similarity', 'full_similarity_score', 'mean_similarity_score']
TARGET_COLUMN = 'mark'
MODEL_BUNDLE_FILENAME = 'grade_model_naive_bayes.pkl'
LOG_FILENAME = 'training_log_naive_bayes.txt'

# -----------------------------
# Load and Process JSON Data
# -----------------------------
def load_and_process_data(json_path):
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        return None

    processed_data = []

    for question_id, question_data in data.items():
        if 'ans' not in question_data:
            continue

        for mark, answer_data in question_data['ans'].items():
            if not all(key in answer_data for key in FEATURE_COLUMNS):
                continue

            row = {
                'question_id': question_id,
                'mark': int(mark),
                'tf_idf_similarity': answer_data.get('tf_idf_similarity', 0.0),
                'full_similarity_score': answer_data.get('full_similarity_score', [0.0])[0]
                    if isinstance(answer_data.get('full_similarity_score'), list)
                    else answer_data.get('full_similarity_score', 0.0),
                'mean_similarity_score': answer_data.get('mean_similarity_score', 0.0)
            }
            processed_data.append(row)

    df = pd.DataFrame(processed_data)
    print(f"Loaded {len(df)} samples with {len(FEATURE_COLUMNS)} features")
    print(f"Mark distribution:\n{df[TARGET_COLUMN].value_counts().sort_index()}")
    return df

# -----------------------------
# Train Gaussian Naive Bayes Model
# -----------------------------
def train_model(df):
    X = df[FEATURE_COLUMNS].values
    y = df[TARGET_COLUMN].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    model = GaussianNB()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    report = classification_report(y_test, y_pred, digits=4)
    print("Classification Report:\n", report)

    with open(LOG_FILENAME, 'w') as f:
        f.write("Features used: " + ", ".join(FEATURE_COLUMNS) + "\n\n")
        f.write("Model: GaussianNB\n\n")
        f.write("Classification Report:\n")
        f.write(report)

    return model

# -----------------------------
# Save Model
# -----------------------------
def save_model(model):
    joblib.dump({
        'model': model,
        'features': FEATURE_COLUMNS
    }, MODEL_BUNDLE_FILENAME)
    print(f"Model saved to '{MODEL_BUNDLE_FILENAME}'")

# -----------------------------
# Entrypoint
# -----------------------------
def main(data_path):
    df = load_and_process_data(data_path)

    if df is None or df.empty:
        print("No valid data found. Exiting.")
        return

    df = df.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN])
    model = train_model(df)
    save_model(model)

# -----------------------------
# Run the Script
# -----------------------------
if __name__ == '__main__':
    data_file = os.path.join("data", "student_full_with_tfidf.json")
    main(data_file)
