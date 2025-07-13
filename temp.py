from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline

# Load model and tokenizer
tokenizer = AutoTokenizer.from_pretrained("oliverguhr/fullstop-punctuation-multilang-large")
model = AutoModelForTokenClassification.from_pretrained("oliverguhr/fullstop-punctuation-multilang-large")

# Create pipeline
nlp = pipeline("token-classification", model=model, tokenizer=tokenizer, aggregation_strategy="simple")

# Input text (without punctuation)
text = "he said good bye while sneezing I'll be back soon"

# Get model predictions
results = nlp(text)

# Build final sentence
punctuated_text = ""
for res in results:
    word = res["word"]
    punct = res["entity_group"]
    punctuated_text += word
    if punct in [".", ",", ":", "!", "?"]:
        punctuated_text += punct
    punctuated_text += " "

# Cleanup and print
punctuated_text = punctuated_text.strip()
print(punctuated_text)
