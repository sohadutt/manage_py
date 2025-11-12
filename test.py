import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
import numpy as np

# ---------------------------------
# 1. THE EXAMPLE DATA
# ---------------------------------
# We create the data directly in the script as a dictionary.
# This makes the script runnable without any external files.
data = {
    'Survived': [0, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1],
    'Pclass':   [3, 1, 3, 1, 3, 3, 1, 3, 3, 2, 3, 3, 2, 3, 3, 2, 3, 1],
    'Sex':      ['male', 'female', 'female', 'female', 'male', 'male', 'male', 'male', 'female', 'female', 'female', 'male', 'female', 'male', 'female', 'female', 'male', 'female'],
    'Age':      [22, 38, 26, 35, 35, np.nan, 54, 2, 27, 14, 4, 20, 58, 39, 14, 55, 2, 31],
    'Fare':     [7.25, 71.28, 7.92, 53.1, 8.05, 8.45, 51.86, 21.07, 11.13, 30.07, 16.7, 7.85, 26.0, 18.0, 7.85, 16.0, 29.12, 146.5]
}

# Convert the dictionary into a pandas DataFrame
df = pd.DataFrame(data)

print("--- 1. Original Data ---")
print(df)
print("\n")


# ---------------------------------
# 2. DATA PREPROCESSING
# ---------------------------------
# We must convert all data into numbers for the model.

# Step 2a: Fill missing 'Age' values with the average (mean) age
# (In our data, one row has a missing 'Age')
df['Age'] = df['Age'].fillna(df['Age'].mean())

# Step 2b: Convert 'Sex' column to numbers
# We map 'male' to 0 and 'female' to 1
df['Sex'] = df['Sex'].map({'male': 0, 'female': 1})

# We'll drop 'Fare' for this simple example to keep it focused
df = df.drop('Fare', axis=1)

print("--- 2. Processed Data (Ready for Model) ---")
print(df)
print("\n")


# ---------------------------------
# 3. DEFINE FEATURES (X) AND TARGET (y)
# ---------------------------------
# 'X' (Features): The columns we use to make a prediction
X = df.drop('Survived', axis=1)

# 'y' (Target): The column we are trying to predict
y = df['Survived']


# ---------------------------------
# 4. SPLIT DATA
# ---------------------------------
# We split our small dataset into a training set and a testing set.
# The model learns from 'train' and is evaluated on 'test'.
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

# print("--- 3. Training Data (X_train) ---")
# print(X_train)
# print("\n")


# ---------------------------------
# 5. TRAIN THE MODEL
# ---------------------------------
# We will use Logistic Regression, a simple and effective model for classification.
print("--- 4. Training the Model... ---")
model = LogisticRegression()

# The model 'learns' the patterns from the training data
model.fit(X_train, y_train)
print("Model trained successfully!")
print("\n")


# ---------------------------------
# 6. EVALUATE THE MODEL
# ---------------------------------
print("--- 5. Evaluating the Model ---")
# Use the trained model to make predictions on the 'test' data
y_pred = model.predict(X_test)

# Compare the model's predictions (y_pred) to the actual answers (y_test)
accuracy = accuracy_score(y_test, y_pred)

print(f"Model Accuracy: {accuracy * 100:.2f}%")
print("\n")

# --- Show the predictions vs. actual answers ---
results = pd.DataFrame({
    'Actual_Survived': y_test,
    'Predicted_Survived': y_pred
})

print("--- Prediction Results (on Test Data) ---")
print(results)