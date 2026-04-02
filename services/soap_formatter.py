import joblib
import re


class SOAPFormatter:

    def __init__(self):
        self.model = joblib.load("app/ml/soap_classifier.pkl")

    def format(self, transcript: str) -> str:
        sentences = self._split_sentences(transcript)

        sections = {"S": [], "O": [], "A": [], "P": []}

        for sentence in sentences:
            if sentence.strip():
                label = self.model.predict([sentence])[0]
                sections[label].append(sentence.strip())

        return self._build_output(sections)

    def _split_sentences(self, text: str):
        return re.split(r'[.?!]', text)

    def _build_output(self, sections):
        output = ""
        for key in ["S", "O", "A", "P"]:
            output += f"{key}:\n"
            for sentence in sections[key]:
                output += f"- {sentence}\n"
            output += "\n"
        return output.strip()