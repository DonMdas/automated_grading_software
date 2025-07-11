# Grade Prediction using K-Nearest Neighbors 

This project aims to predict student grades based on their answers using a K-Nearest Neighbors (KNN) model. The model is trained on features extracted from student answers, including TF-IDF similarity, full similarity score, and mean similarity score.

## Directory Structure

- `grade_prediction_knearest.py`: The main Python script for training the KNN model.
- `Processed Answer/`: This directory contains the processed JSON data.
  - `answer_key.json`: Contains the questions and their corresponding ideal answers.
  - `answer_key_with_structure.json`: Contains the questions, ideal answers, and a structured breakdown of the key points in the ideal answers.
  - `student_answer.json`: Contains student answers for each question, categorized by the marks awarded (0-10).
  - `student_answer_with_structure.json`: Contains student answers with a structured breakdown, likely used as the base for feature extraction.
- `Raw Answers/`: This directory contains the raw source material for the questions and answers. (Satwik collected the data)
  - `CBSE 9 MLQB - English Language & Literature.pdf`: Source PDF for English Language & Literature questions.
  - `Item-Bank-----English---Class-9 rubric.pdf`: Source PDF for the English rubric.
  - `supportmaterialeng9.pdf`: Supporting material for the English curriculum.

## Training Process

The training process is handled by the `grade_prediction_knearest.py` script, which performs the following steps:

1.  **Load and Process Data**: The script loads the training data from a JSON file. It expects a file named `student_full_with_tfidf.json` in a `data/` directory. This file should contain the following features for each student answer:
    *   `tf_idf_similarity`
    *   `full_similarity_score`
    *   `mean_similarity_score`
    The target variable is the `mark` awarded to the answer.

2.  **Hyperparameter Tuning**: The script uses `GridSearchCV` to find the best hyperparameters for the KNN model. It tunes the following parameters:
    *   `n_neighbors`: [3, 5, 7, 9]
    *   `weights`: ['uniform', 'distance']
    *   `p`: [1, 2] (Manhattan and Euclidean distances)

3.  **Train Model**: The script trains the KNN model on the processed data using the best hyperparameters found in the tuning step.

4.  **Evaluate Model**: The model is evaluated using a classification report, which includes precision, recall, and F1-score for each mark. The evaluation results are saved to `training_log_knn.txt`.

5.  **Save Model**: The trained model and the feature columns used for training are saved to a file named `grade_model_knn.pkl` using `joblib`.




