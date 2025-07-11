import json
from transformers import BertTokenizer, BertModel
import torch
import os
import logging
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load pre-trained BERT tokenizer and model (uncased)
try:
    tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
    model = BertModel.from_pretrained("bert-base-uncased")
    logger.info("BERT model and tokenizer loaded successfully")
except Exception as e:
    logger.error(f"Failed to load BERT model: {str(e)}")
    sys.exit(1)

def get_mean_pooled_embedding(text):
    try:
        # Ensure text is a string
        if not isinstance(text, str):
            text = str(text)
        
        # Tokenize input
        inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
        
        # Forward pass to get hidden states
        with torch.no_grad():
            outputs = model(**inputs)
        
        last_hidden_state = outputs.last_hidden_state  # shape: [batch_size, seq_len, hidden_dim]
        attention_mask = inputs['attention_mask']      # shape: [batch_size, seq_len]

        # Expand mask to match hidden size
        mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()

        # Mean pooling: sum(hidden * mask) / sum(mask)
        summed = torch.sum(last_hidden_state * mask, dim=1)
        counted = torch.clamp(mask.sum(dim=1), min=1e-9)
        mean_pooled = summed / counted

        return mean_pooled.squeeze().numpy()  # Shape: (hidden_dim,)
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        raise

def answer_key_embeddings(datapath):
    try:
        # Use os.path.join for cross-platform compatibility
        input_path = os.path.join(datapath, 'answer_key_with_structure.json')
        output_path = os.path.join(datapath, 'answer_key_with_embeddings.json')
        
        # Check if input file exists
        if not os.path.exists(input_path):
            logger.error(f"Input file not found: {input_path}")
            return False
            
        with open(input_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                logger.info(f"Successfully loaded data from {input_path}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {str(e)}")
                return False
        
        # Process count for logging
        total_items = sum(len(data[q_no]['structure']) for q_no in data)
        processed_items = 0
        
        for q_no in data:
            try:
                structure = data[q_no]['structure']
                for key in structure:
                    try:
                        content = structure[key]
                        if content is None:
                            content = ""
                        elif isinstance(content, str):
                            content = content.strip()
                        else:
                            content = str(content).strip()
                            
                        cont_embedding = get_mean_pooled_embedding(content)
                        data[q_no]['structure'][key] = {
                            'content': content,
                            'embedding': cont_embedding.tolist()  # Convert to list for JSON serialization
                        }
                        
                        processed_items += 1
                        if processed_items % 10 == 0:
                            logger.info(f"Processed {processed_items}/{total_items} items")
                            
                    except Exception as e:
                        logger.warning(f"Error processing item {q_no}.{key}: {str(e)}")
                        # Use empty embedding if processing fails
                        data[q_no]['structure'][key] = {
                            'content': content if 'content' in locals() else "",
                            'embedding': []
                        }
            except KeyError as e:
                logger.warning(f"Missing key in question {q_no}: {str(e)}")
                continue
                
        # Save the updated data with embeddings
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Successfully saved embeddings to {output_path}")
            return True
        except IOError as e:
            logger.error(f"Error writing output file: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Unexpected error in answer_key_embeddings: {str(e)}")
        return False

if __name__ == "__main__":
    try:
        datapath = "data"
        if not os.path.exists(datapath):
            logger.error(f"Data directory not found: {datapath}")
            sys.exit(1)
            
        success = answer_key_embeddings(datapath)
        if success:
            print("Answer key embeddings generated and saved successfully.")
        else:
            print("Failed to generate answer key embeddings. Check logs for details.")
    except Exception as e:
        logger.error(f"Main execution error: {str(e)}")
        print(f"An error occurred: {str(e)}")
        sys.exit(1)



