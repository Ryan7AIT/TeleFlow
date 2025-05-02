import re
from sentence_transformers import SentenceTransformer, util

# Load sentence embedding model (multi-language capable)
model = SentenceTransformer('distiluse-base-multilingual-cased-v2')

# Define your command intents and example phrases in English only
intent_phrases = {
    "add_client": [
        "add client", "add a customer", "register client", "register a new customer",
        "insert client", "create new client", "new customer"
    ],
    "delete_client": [
        "delete client", "remove customer", "erase client", "remove a client"
    ],
    # Add more commands as needed...
}

# Clean user input across multiple languages
def clean_user_input(text):
    remove_patterns = [
        # English
        r"what would you like to do\??",
        r"how can i help you.*",
        r"please",
        r"^i(?:'d)? like to",
        r"^can you",
        r"^i want to",

        # French
        r"je veux",
        r"s'?il vous plaît",
        r"pouvez-vous",
        r"je voudrais",

        # Arabic
        r"من فضلك",
        r"أريد",
        r"هل يمكنك",
    ]

    for pattern in remove_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
    return text

# Precompute embeddings for all intent phrases
intent_embeddings = []
intent_lookup = []

for intent, phrases in intent_phrases.items():
    for phrase in phrases:
        embedding = model.encode(phrase, convert_to_tensor=True)
        intent_embeddings.append(embedding)
        intent_lookup.append((intent, phrase))

# Main matcher function
def match_intent(user_input):
    cleaned = clean_user_input(user_input)
    user_embedding = model.encode(cleaned, convert_to_tensor=True)

    best_score = 0
    best_intent = None
    matched_phrase = None

    for emb, (intent, phrase) in zip(intent_embeddings, intent_lookup):
        score = util.cos_sim(user_embedding, emb).item()
        if score > best_score:
            best_score = score
            best_intent = intent
            matched_phrase = phrase

    return best_intent, matched_phrase, best_score

# Example usage
if __name__ == "__main__":
    while True:
        user_input = input("🗣️ What would you like to do? ")
        intent, phrase, score = match_intent(user_input)

        print("\n🧠 Best Match:", intent)
        print("🔍 Matched Phrase:", f'"{phrase}"')
        print("📊 Confidence Score:", round(score, 2))

        if score < 0.65:
            print("⚠️ Not confident in match. You may want to ask the user to rephrase.\n")
        else:
            print("✅ Confident match.\n")
    