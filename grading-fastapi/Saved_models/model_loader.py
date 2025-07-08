import joblib

model_bundle = joblib.load("Saved_models/grade_model_knn.pkl")
model = model_bundle['model']
features = model_bundle['features']
print("Expected features:", features)