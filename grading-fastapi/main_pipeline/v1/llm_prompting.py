import ollama
import json
import logging

def invoke_llm(model_name, prompt):
    """
    Invoke an Ollama language model with the provided prompt.
    
    Args:
        model_name (str): Name of the Ollama model to use
        prompt (str): The prompt to send to the model
        
    Returns:
        str: The model's response content if successful
        
    Raises:
        ValueError: If model_name or prompt is invalid
        ConnectionError: If there's an issue connecting to Ollama
        KeyError: If the response structure is unexpected
        Exception: For any other unexpected errors
    """
    if not model_name or not isinstance(model_name, str):
        raise ValueError("Model name must be a non-empty string")
    
    if not prompt or not isinstance(prompt, str):
        raise ValueError("Prompt must be a non-empty string")
    
    try:
        # Call the Ollama API
        response = ollama.chat(
            model=model_name,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Validate response structure
        if not hasattr(response, 'message'):
            raise AttributeError("Unexpected response structure: 'message' attribute not found")

        if not hasattr(response.message, 'content'):
            raise AttributeError("Unexpected response structure: 'content' attribute not found in message")

        return response.message.content
    
    except ollama.RequestError as e:
        logging.error(f"Ollama API request failed: {str(e)}")
        raise ConnectionError(f"Failed to connect to Ollama API: {str(e)}")
    
    except KeyError as e:
        logging.error(f"Unexpected response structure: {str(e)}")
        raise
    
    except Exception as e:
        logging.error(f"Unexpected error when invoking LLM: {str(e)}")
        raise


# Example usage
if __name__ == "__main__":
    try:
        data_path = "data/student_answer_training.json"
        data_path1 = "data/answer_key_with_structure.json"
        model_name = "structure_mapper"
        
        with open(data_path, "r") as f:
            student_answer = json.load(f)
        
        with open(data_path1, "r") as f:
            answer_key = json.load(f)


        prompt = "structure - :" + str(answer_key["1"]["structure"].keys()) +"\nstudent_answer - :" + str(student_answer['1']['ans']['5'])
        response = invoke_llm(model_name, prompt)
        print(response)
        try:
            # Convert response to a dictionary
            response_dict = json.loads(response)
            for key in response_dict.keys():
                print(f"{key}: {response_dict[key]}")
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse response as JSON: {str(e)}")
            print("Raw response:", response)
        
    except FileNotFoundError:
        print(f"Error: File not found at {data_path}")
    except KeyError as e:
        print(f"Error: Key not found in answer_key: {str(e)}")
    except ValueError as e:
        print(f"Error: Invalid input: {str(e)}")
    except ConnectionError as e:
        print(f"Error: Connection failed: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")

