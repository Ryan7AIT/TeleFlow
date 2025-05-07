import json
import os
from sentence_transformers import SentenceTransformer, util
from thefuzz import fuzz
import time

# Load commands from state.py
def load_test_commands():
    commands = {}
    commands_dir = "commands"
    
    # Check if commands directory exists
    if not os.path.exists(commands_dir):
        print("Commands directory not found. Using sample commands.")
        return {"help": {}, "about": {}, "settings": {}}
    
    for file in os.listdir(commands_dir):
        if file.endswith(".json"):
            try:
                with open(os.path.join(commands_dir, file), "r") as f:
                    file_commands = json.load(f)
                    commands.update(file_commands)
            except Exception as e:
                print(f"Error loading {file}: {str(e)}")
    
    return commands

def clean_user_input(text):
    """Demo of input cleaning function."""
    return text.lower().strip()

def main():
    print("Loading SentenceTransformer model (this might take a moment)...")
    model = SentenceTransformer('distiluse-base-multilingual-cased-v2')
    print("Model loaded!")
    
    commands = load_test_commands()
    command_keys = list(commands.keys())
    
    # Precompute embeddings
    print("Precomputing command embeddings...")
    start_time = time.time()
    command_embeddings = []
    for cmd in command_keys:
        embedding = model.encode(cmd, convert_to_tensor=True)
        command_embeddings.append(embedding)
    precompute_time = time.time() - start_time
    print(f"Precomputing {len(command_keys)} embeddings took {precompute_time:.4f} seconds")
    
    while True:
        test_input = input("\nEnter a test phrase (or 'q' to quit): ")
        if test_input.lower() == 'q':
            break
            
        cleaned_input = clean_user_input(test_input)
        
        # Semantic matching
        start_time = time.time()
        text_embedding = model.encode(cleaned_input, convert_to_tensor=True)
        
        best_semantic_match = None
        best_semantic_score = 0
        
        for idx, (cmd, emb) in enumerate(zip(command_keys, command_embeddings)):
            score = util.cos_sim(text_embedding, emb).item()
            if score > best_semantic_score:
                best_semantic_score = score
                best_semantic_match = cmd
        
        semantic_time = time.time() - start_time
        
        # Fuzzy matching
        start_time = time.time()
        best_fuzzy_match = None
        best_fuzzy_score = 0
        
        for cmd in command_keys:
            score = fuzz.ratio(cleaned_input, cmd) / 100.0
            if score > best_fuzzy_score:
                best_fuzzy_score = score
                best_fuzzy_match = cmd
        
        fuzzy_time = time.time() - start_time
        
        # Combined approach
        start_time = time.time()
        best_combined_match = None
        best_combined_score = 0
        
        for idx, (cmd, emb) in enumerate(zip(command_keys, command_embeddings)):
            semantic_score = util.cos_sim(text_embedding, emb).item()
            fuzzy_score = fuzz.ratio(cleaned_input, cmd) / 100.0
            
            # 70% semantic, 30% fuzzy
            combined_score = (0.7 * semantic_score) + (0.3 * fuzzy_score)
            
            if combined_score > best_combined_score:
                best_combined_score = combined_score
                best_combined_match = cmd
        
        combined_time = time.time() - start_time
        
        # Print results
        print("\n--- Results ---")
        print(f"Input: '{test_input}'")
        print(f"Semantic match: '{best_semantic_match}' (score: {best_semantic_score:.4f}, time: {semantic_time:.4f}s)")
        print(f"Fuzzy match: '{best_fuzzy_match}' (score: {best_fuzzy_score:.4f}, time: {fuzzy_time:.4f}s)")
        print(f"Combined match: '{best_combined_match}' (score: {best_combined_score:.4f}, time: {combined_time:.4f}s)")
        
        print("\nWould match?" if best_combined_score >= 0.65 else "\nWould NOT match!")

if __name__ == "__main__":
    main() 