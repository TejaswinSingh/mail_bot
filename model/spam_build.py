import pandas as pd
from sklearn.preprocessing import LabelEncoder
import pickle
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score


df = pd.read_csv('mail_data_training.csv')
df.head()

df.info()

# Preprocess the data
le = LabelEncoder()
df['Category'] = le.fit_transform(df['Category'])

# Convert text to lowercase
df['Message'] = df['Message'].str.lower()



# Split the data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(df['Message'], df['Category'], test_size=0.2, random_state=42)

# Create the Bag-of-Words feature vectors
vectorizer = CountVectorizer()
X_train_bow = vectorizer.fit_transform(X_train)
X_test_bow = vectorizer.transform(X_test)



# Train the Naive Bayes classifier
model = MultinomialNB()
model.fit(X_train_bow, y_train)



# Make predictions on the test set
y_pred = model.predict(X_test_bow)

# Calculate evaluation metrics
accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
f1 = f1_score(y_test, y_pred)

print("Accuracy:", accuracy)
print("Precision:", precision)
print("Recall:", recall)
print("F1-score:", f1)

# Get user input
text = input("Enter a message: ")

# Preprocess the user input
text = text.lower()

# Convert the input text to a feature vector
text_vector = vectorizer.transform([text])

# Make a prediction
prediction = model.predict(text_vector)[0]
predicted_label = le.inverse_transform([prediction])[0]

print("Predicted Label:", predicted_label)

sentences = [
    "Congratulations! You've won a free vacation package.",
    "URGENT: Your account needs verification, click here to proceed.",
    "Get rich quick! Double your money in just one week.",
    "Limited time offer: Buy now and save 50% off!",
    "Claim your prize! You are the lucky winner!",
    "Make money from home with our proven system.",
    "You've been selected for a special discount offer!",
    "Attention: Your email has been randomly chosen to win a prize.",
    "Act now and get a free trial of our exclusive product.",
    "Increase your website traffic with our guaranteed SEO service."
]

result = []
for text in sentences:
  # Preprocess the user input
  text = text.lower()

  # Convert the input text to a feature vector
  text_vector = vectorizer.transform([text])

  # Make a prediction
  prediction = model.predict(text_vector)[0]
  predicted_label = le.inverse_transform([prediction])[0]
  result.append((text, predicted_label))

print(result)

# Save the model
with open('spam_model.pkl', 'wb') as file:
    pickle.dump(model, file)
# Save the vectorizer
with open('vectorizer.pkl', 'wb') as f:
    pickle.dump(vectorizer, f)
with open('label_encoder.pkl', 'wb') as f:
    pickle.dump(le, f)