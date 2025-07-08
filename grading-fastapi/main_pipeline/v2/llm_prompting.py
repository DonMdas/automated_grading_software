import os
import google.generativeai as genai
from google.generativeai import types
from dotenv import load_dotenv
import json
import logging
import time
import re

# Load environment variables
load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Global dictionary for system instructions
SYSTEM_INSTRUCTIONS = {
"breakdown_model": "You're a teaching assistant who will break down each answer into a structured JSON object. Your output must be a single JSON object with two top-level keys: 'breakdown' and 'requires_llm_evaluation'.\n\n1.  **'breakdown' key**: The value for this key will be another JSON object. In this inner object, you will break down the provided answer key into different parts. The keys will be the category names (e.g., 'definition', 'explanation', 'example'), and the values will be the corresponding text from the answer key. \n    *   **Category Creation**: If I do not provide a structure (a list of categories), you must decide on suitable categories based on the nature of the answer. If I provide a structure/classes, you must use those exact categories. Everything from the answer key must be mapped to a category.\n    *   **Rules for Provided Structure**: If a category in the provided structure is missing from the answer, keep the category key but assign it an empty string value (''). Do not add any extra categories from the student answer if a structure is already given. The content of the output values must only include text from the student answer.\n\n2.  **'requires_llm_evaluation' key**: The value for this key will be a list of strings. This list must contain the names of any category from your 'breakdown' object that requires the student to invent or provide a concrete, specific instance, illustration, or scenario. This is a strict rule. Only include category names like 'Example', 'Use Case', 'Illustration', or 'Scenario'. Do NOT include categories for describing, defining, explaining, summarizing, or stating an opinion (e.g., 'Definition', 'Fact', 'Explanation', 'Opinion', 'Conclusion', 'Reason').\n\n**General Rules**:\n*   I will provide a question and an answer key. The question is for context only. Do *not* include the question in the output.\n*   The final output must be a single, valid JSON object that can be parsed directly. \n*   The 'breakdown' object must be flat (no nested objects).\n*   Values should be pure text (strings). Do not use newlines or extra spaces within the strings.\n\n**Example 1 (Analytical Categories)**:\nQuestion: Describe how the author shows the emotional transformation of the character in \"The Lost Child\".\nAnswer: The story begins with the child being curious and excited about the fair, constantly asking for toys, sweets, and balloons. However, once he realizes he is lost, his priorities shift dramatically. He no longer wants material things and instead cries for his parents. This emotional transition highlights the depth of a child’s attachment to their caregivers over worldly pleasures.\nExpected Output:\n{\n  \"breakdown\": {\n    \"initial_emotion\": \"The story begins with the child being curious and excited about the fair, constantly asking for toys, sweets, and balloons.\",\n    \"emotional_shift\": \"However, once he realizes he is lost, his priorities shift dramatically.\",\n    \"final_emotion\": \"He no longer wants material things and instead cries for his parents.\",\n    \"interpretation\": \"This emotional transition highlights the depth of a child’s attachment to their caregivers over worldly pleasures.\"\n  },\n  \"requires_llm_evaluation\": []\n}\n\n**Example 2 (Invented Instance Category)**:\nQuestion: Define 'photosynthesis' and give an example of an organism that uses it.\nAnswer: Photosynthesis is the process used by plants and algae to convert light energy into chemical energy, which they use as food. For example, a large oak tree performs photosynthesis in its leaves.\nExpected Output:\n{\n  \"breakdown\": {\n    \"definition\": \"Photosynthesis is the process used by plants and algae to convert light energy into chemical energy, which they use as food.\",\n    \"example\": \"For example, a large oak tree performs photosynthesis in its leaves.\"\n  },\n  \"requires_llm_evaluation\": [\"example\"]\n}",
"special_case_check": "You are given a label representing a type of student answer. Your task is to apply one strict rule: Respond with 'no' if and only if the label requires the student to invent or provide a concrete, specific instance, illustration, or scenario. This category is exclusively for labels like 'Example' and 'Use Case'. For ALL other labels that involve describing, defining, explaining, summarizing, or stating an opinion, you must respond with 'yes'. There are no other exceptions. Label: <INSERT LABEL HERE> Your Answer: examples; Fact - yes: A statement of fact is descriptive, not the creation of a new instance. Definition - yes: A definition describes a concept, it does not invent an example of it. Example - no: This label explicitly requires inventing/providing a specific instance. Opinion - yes: An opinion is a student's statement to be analyzed, not a new instance they must invent. Explanation - yes: An explanation describes a process or concept; it does not generate a novel case. Use Case - no: This requires inventing a specific application or scenario, which is a type of instance. Emotion - yes: A statement of emotion is descriptive, not the creation of a new instance. Conclusion - yes: A conclusion summarizes information, it does not invent a new example.",
"special_case_evaluation": "Evaluate the student's response based on the following 5 criteria. Each criterion should be rated on a scale of 0 to 2 (0 = Poor, 1 = Partial, 2 = Excellent). Provide a total score out of 10.\n\nThe whole answer won't be given just a particular part of it - example/use case/opinion etc. So just evaluate that.\nCriterion\nWhat to Look For\nScore Range\n1. Relevance\nDoes the student’s example/use case directly relate to the question and the concept being tested?\n0–2\n2. Appropriateness\nIs the example suitable in tone, level, and context for a CBSE 9th/10th grade answer?\n0–2\n3. Correctness/Accuracy\nDoes the example demonstrate a correct understanding of the underlying idea from the text?\n0–2\n4. Specificity\nIs the example specific and detailed, rather than vague or generic?\n0–2\n5. Originality/Insight\nDoes the example show some depth of thought, creativity, or unique insight (beyond rote memorization)?\n0–2\n\n\nJust give the score as integer. No explanation or anything required.\n\neg:\n\n9\n",
"structure_mapper": "Your'e a teaching assistant who will breakdown each answers into different parts - for eg- a part of the answer will be for defn, some part for expln etc. \ni will be giving you the category labels. you just have to map the parts of the answer to these labels.\nInclude everything from the answer.\noutput should be just json.\nno nested elements should be there\n\neg:\nstructure: [defn,interpretation_of_traveller's_dilemma],\n\nanswer: The traveller is in a dilemma so as to which road he must choo\n... se. One is more travelled and weary but the other is less travelled and overgrown with grass and less worn out. So the poet is inclined to cho\n... ose the other road as it is less walked over.}\n\noutput:\n\n{\n  \"defn\": \"The phrase describes two different paths: one that has been heavily traveled, showing signs of wear from frequent use; and \nanother path which appears untouched or little used.\",\n  \"interpretation_of_traveller's_dilemma\": \"The traveller feels uncertain about choosing the correct road. The more worn-out route seems \nfamiliar but perhaps less appealing due to its overuse, while the grassier option suggests it is newer and uncharted.\"\n\nnote: if a category is not found in the answer. Keep the category label in the result and map it to empty string.\n\nnote: also no nested json objects. one level of categorisation is enough.\nnote: also if a category in student response is missing when compared to the answer structure, just keep the category empty, do not fill it with any explanation. Do not add any extra categories from the student answer if the structure is already given along with it in json. And in the content of the output do not include anything from the structure given by me, it should only include content from the student answer\n\nImportant: no nested json object should be there. The value should be pure text no json,no list nothing. Just text(string).!!. Should be a proper json object - do not miss the commas between the objects. I will be using json.load fn on the output so make sure your output is properly parsable. avoid new lines and extra spaces.\n"
}

def invoke_llm(model_name, prompt):
    """
    Invoke a Gemma language model with the provided prompt.
    
    Args:
        model_name (str): Name of the Gemma model to use
        prompt (str): The prompt to send to the model
        
    Returns:
        str: The model's response content if successful
        
    Raises:
        ValueError: If model_name or prompt is invalid
        ConnectionError: If there's an issue connecting to the API
        Exception: For any other unexpected errors
    """
    if not model_name or not isinstance(model_name, str):
        raise ValueError("Model name must be a non-empty string")
    
    if not prompt or not isinstance(prompt, str):
        raise ValueError("Prompt must be a non-empty string")
    
    max_retries = 5  # Maximum number of retry attempts
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Get system instruction for the model
            system_instruction = SYSTEM_INSTRUCTIONS.get(model_name, "")
            
            prompt += "\n\n do not include any extra information. just give the required json output.\n\n"  # Ensure prompt ends with a newline for clarity
            
            # Combine system instruction with user prompt
            full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
            
            # Initialize the model
            model = genai.GenerativeModel(model_name="gemma-3-27b-it")
            
            contents = [
                {
                    "role": "user",
                    "parts": [
                        {"text": full_prompt},
                    ],
                },
            ]
            
            generate_content_config = types.GenerationConfig(
                response_mime_type="text/plain",
            )
            
            # Generate response
            response = model.generate_content(
                contents=contents,
                generation_config=generate_content_config
            )
            
            if not response or not response.text:
                raise AttributeError("Unexpected response structure: no text content found")
            
            return response.text
            
        except Exception as e:
            error_message = str(e)
            
            # Check if it's a rate limit error (429)
            if "429" in error_message and "quota" in error_message.lower():
                retry_count += 1
                
                # Extract retry delay from error message
                retry_delay = 30  # default delay
                try:
                    # Look for retry_delay in the error message
                    delay_match = re.search(r'retry_delay.*?seconds: (\d+)', error_message)
                    if delay_match:
                        retry_delay = int(delay_match.group(1))
                except:
                    pass  # Use default delay if parsing fails
                
                if retry_count < max_retries:
                    logging.warning(f"Rate limit exceeded. Retrying in {retry_delay} seconds... (Attempt {retry_count}/{max_retries})")
                    print(f"Rate limit exceeded. Retrying in {retry_delay} seconds... (Attempt {retry_count}/{max_retries})")
                    time.sleep(retry_delay)
                    continue
                else:
                    logging.error(f"Max retries ({max_retries}) exceeded for rate limiting")
                    raise ConnectionError(f"Rate limit exceeded after {max_retries} attempts: {error_message}")
            else:
                # For non-rate-limit errors, don't retry
                logging.error(f"Gemma API request failed: {error_message}")
                raise ConnectionError(f"Failed to connect to Gemma API: {error_message}")
    
    # This should never be reached due to the logic above, but just in case
    raise ConnectionError(f"Failed to get response after {max_retries} attempts")

# Example usage
if __name__ == "__main__":
    try:
        data_path = "data/student_answer_training.json"
        data_path1 = "data/answer_key_with_structure.json"
        model_name = "breakdown_model"  # Changed to use structure_mapper model

        with open(data_path, "r") as f:
            student_answer = json.load(f)
        
        with open(data_path1, "r") as f:
            answer_key = json.load(f)

        prompt = "structure - :" + str(answer_key["10"]["structure"].keys()) +"\nstudent_answer - :" + str(student_answer['10']['ans']['5'])
        prompt1 = str(answer_key["1"]["answer"])
        response = invoke_llm(model_name, prompt1)
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

