import json
import pandas as pd
import numpy as np
import xgboost as xgb
import joblib
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import classification_report
import os

# -----------------------------
# Configs
# -----------------------------
FEATURE_COLUMNS = ['tf_idf_similarity', 'full_similarity_score', 'mean_similarity_score']
TARGET_COLUMN = 'mark'
MODEL_FILENAME = 'grade_predictor.json'
MODEL_BUNDLE_FILENAME = 'grade_model_bundle.pkl'
LOG_FILENAME = 'training_log.txt'

# -----------------------------
# Load and Process JSON Data
# -----------------------------
def load_and_process_data(json_path):
    """
    Load the student_full_with_tfidf.json file and extract the relevant features
    """
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        return None
    
    # Initialize lists to store extracted data
    processed_data = []
    
    # Iterate through each question
    for question_id, question_data in data.items():
        if 'ans' not in question_data:
            continue
            
        # Iterate through each answer (mark level)
        for mark, answer_data in question_data['ans'].items():
            # Skip entries with missing features
            if not all(key in answer_data for key in ['tf_idf_similarity', 'full_similarity_score', 'mean_similarity_score']):
                continue
                
            # Extract features
            row = {
                'question_id': question_id,
                'mark': int(mark),  # Convert mark to integer
                'tf_idf_similarity': answer_data.get('tf_idf_similarity', 0.0),
                'full_similarity_score': answer_data.get('full_similarity_score', [0.0])[0] 
                    if isinstance(answer_data.get('full_similarity_score', [0.0]), list) 
                    else answer_data.get('full_similarity_score', 0.0),
                'mean_similarity_score': answer_data.get('mean_similarity_score', 0.0)
            }
            processed_data.append(row)
    
    # Convert to DataFrame
    df = pd.DataFrame(processed_data)
    
    # Print data summary
    print(f"Loaded {len(df)} samples with {len(FEATURE_COLUMNS)} features")
    print(f"Mark distribution: \n{df[TARGET_COLUMN].value_counts().sort_index()}")
    
    return df

# -----------------------------
# Hyperparameter Tuning
# -----------------------------
def tune_model(X_train, y_train):
    model = xgb.XGBClassifier(
        objective='multi:softmax',
        num_class=11,  # 0-10 marks
        use_label_encoder=False,
        eval_metric='mlogloss'
    )

    param_grid = {
        'max_depth': [3, 4, 5],
        'learning_rate': [0.05, 0.1, 0.2],
        'n_estimators': [50, 100, 200],
        'subsample': [0.8, 1.0]
    }

    grid = GridSearchCV(model, param_grid, cv=3, scoring='accuracy', verbose=1)
    grid.fit(X_train, y_train)

    print(f"Best Parameters: {grid.best_params_}")
    return grid.best_estimator_, grid.best_params_

# -----------------------------
# Train Model
# -----------------------------
def train_model(df):
    X = df[FEATURE_COLUMNS].values
    y = df[TARGET_COLUMN].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    model, best_params = tune_model(X_train, y_train)
    y_pred = model.predict(X_test)

    report = classification_report(y_test, y_pred, digits=4)
    print("Classification Report:\n", report)

    # Log training details
    with open(LOG_FILENAME, 'w') as f:
        f.write("Features used: " + ", ".join(FEATURE_COLUMNS) + "\n\n")
        f.write("Best Parameters:\n")
        f.write(str(best_params) + "\n\n")
        f.write("Classification Report:\n")
        f.write(report)

    return model

# -----------------------------
# Save Model and Metadata
# -----------------------------
def save_model(model):
    model.save_model(MODEL_FILENAME)
    joblib.dump({
        'model': model,
        'features': FEATURE_COLUMNS
    }, MODEL_BUNDLE_FILENAME)
    print(f"Model saved to '{MODEL_FILENAME}' and '{MODEL_BUNDLE_FILENAME}'")

# -----------------------------
# Entrypoint
# -----------------------------
def main(data_path):
    # Load and process data from the student_full_with_tfidf.json file
    df = load_and_process_data(data_path)
    
    if df is None or df.empty:
        print("No valid data found. Exiting.")
        return
    
    # Drop rows with NaN values
    df = df.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN])
    
    # Train the model
    model = train_model(df)
    
    # Save the model
    save_model(model)

# -----------------------------
# Run the script
# -----------------------------
if __name__ == '__main__':
    data_file = os.path.join("data", "student_full_with_tfidf.json")
    main(data_file)
