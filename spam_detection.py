import pickle
import sklearn


class Spam_Detection_Model:
    def __init__(self):
        with open(r"model/spam_model.pkl", "rb") as file:
            self.__model = pickle.load(file)

        with open(r"model/vectorizer.pkl", "rb") as file:
            self.__vectorizer = pickle.load(file)

        with open(r"model/label_encoder.pkl", "rb") as file:
            self.__le = pickle.load(file)

    def classify(self, text):
        text_vector = self.__vectorizer.transform([text])
        prediction = self.__model.predict(text_vector)[0]
        prediction_label = self.__le.inverse_transform([prediction])[0]
        return str(prediction_label)