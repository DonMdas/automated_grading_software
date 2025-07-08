import json
import srsly
import os

def stringify_structure(value):
    """
    Recursively converts non-string structure values into a single coherent string.
    This is essential for handling complex/nested structure values.
    """
    if isinstance(value, str):
        # Clean up string from extra quotes and leading/trailing whitespace
        return value.strip().replace('"', '')
    if isinstance(value, list):
        return " ".join([stringify_structure(item) for item in value])
    if isinstance(value, dict):
        # If the dict contains a 'content' key, prioritize that. Otherwise, join all values.
        if 'content' in value:
            return stringify_structure(value['content'])
        return " ".join([stringify_structure(v) for v in value.values()])
    return str(value)

def create_constructed_task(q_id, question, structure_dict, original_answer, other_meta={}):
    """
    A central function to build a Prodigy task by constructing text from a structure dictionary.
    
    Args:
        q_id (str): The question ID.
        question (str): The question text.
        structure_dict (dict): The dictionary defining the answer's structure.
        original_answer (str): The original, real answer text for reference.
        other_meta (dict): Any additional metadata to include in the task.
        
    Returns:
        dict: A Prodigy-compatible task dictionary.
    """
    separator = "\n\n"
    constructed_parts = []
    annotated_spans = []
    current_offset = 0
    
    # Get similarity scores if available
    similarity_scores = other_meta.get("structure_similarity_scores", [])
    labels = list(structure_dict.keys())

    for i, (label, structure_value) in enumerate(structure_dict.items()):
        part_text = stringify_structure(structure_value)
        if not part_text:
            continue

        constructed_parts.append(part_text)
        
        start = current_offset
        end = start + len(part_text)
        
        # Create label with similarity score if available
        display_label = label
        if i < len(similarity_scores):
            score = similarity_scores[i]
            display_label = f"{label} (sim: {score:.3f})"
        
        annotated_spans.append({
            "start": start,
            "end": end,
            "label": display_label,
            "source": "constructed_v2"
        })
        
        current_offset = end + len(separator)

    final_text = separator.join(constructed_parts)
    
    # Prepare metadata for Prodigy UI (exclude similarity scores since they're now in labels)
    meta_data = {
        "id": q_id,
        "question": question,
        "original_answer": original_answer
    }
    # Add other metadata but exclude structure_similarity_scores since we're displaying them inline
    filtered_meta = {k: v for k, v in other_meta.items() if k != "structure_similarity_scores"}
    meta_data.update(filtered_meta)

    # Create labels list with similarity scores for config
    config_labels = []
    for i, label in enumerate(labels):
        if i < len(similarity_scores):
            config_labels.append(f"{label} (sim: {similarity_scores[i]:.3f})")
        else:
            config_labels.append(label)

    return {
        "text": final_text,
        "spans": annotated_spans,
        "meta": meta_data,
        "config": {
            "labels": config_labels
        }
    }

def process_answer_key_file(filepath):
    """Processes the teacher's answer key file."""
    print(f"Processing answer key file: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tasks = []
    for q_id, content in data.items():
        if "answer" not in content or "structure" not in content:
            continue
            
        task = create_constructed_task(
            q_id=q_id,
            question=content.get("question", "N/A"),
            structure_dict=content["structure"],
            original_answer=content["answer"]
        )
        tasks.append(task)
    print(f"-> Found and processed {len(tasks)} tasks from the answer key.")
    return tasks

def process_student_answers_file(filepath):
    """Processes a student's processed answers file (like s1_processed.json)."""
    print(f"Processing student answers file: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tasks = []
    for q_id, content in data.items():
        if "original_answer" not in content or "structure" not in content:
            continue

        # Prepare other metadata, excluding large or redundant fields
        other_meta = {
            k: v for k, v in content.items() 
            if k not in ["original_answer", "structure", "embedding"]
        }

        task = create_constructed_task(
            q_id=q_id,
            # Student files might not have the question, so handle its absence
            question=content.get("question", f"Student Answer for Q#{q_id}"),
            structure_dict=content["structure"],
            original_answer=content["original_answer"],
            other_meta=other_meta
        )
        tasks.append(task)
    print(f"-> Found and processed {len(tasks)} tasks from student answers.")
    return tasks

def main(answer_key_path, student_answer_path, output_path):
    """
    Main function to process both files and generate a single .jsonl output.
    """
    # Process both files
    answer_key_tasks = process_answer_key_file(answer_key_path)
    student_tasks = process_student_answers_file(student_answer_path)
    
    # Combine the tasks from both sources
    all_tasks = answer_key_tasks + student_tasks
    
    # Write to the final .jsonl file
    srsly.write_jsonl(output_path, all_tasks)
    print(f"\n✅ Success! Created '{output_path}' with a total of {len(all_tasks)} tasks.")
    print("You can now run this file in Prodigy, for example:")
    print(f"prodigy spans.manual your_dataset_name blank:en {output_path} --label TEMP")

if __name__ == "__main__":
    # --- Define your file paths here ---
    # Note: I am creating dummy files for the script to run without error.
    # You should replace these with your actual file paths.
    
    # Create a dummy data directory if it doesn't exist
    if not os.path.exists("data"):
        os.makedirs("data")

    # Dummy answer key file (replace with your real file)
    ANSWER_KEY_FILE = "data/answer_key_with_structure.json"
    if not os.path.exists(ANSWER_KEY_FILE):
        srsly.write_json({"1": {"question": "Q1", "answer": "Ans1", "structure": {"intro": "Intro1"}}}, ANSWER_KEY_FILE)

    # Dummy student answer file (replace with your real file)
    STUDENT_FILE = "data/s1_processed.json"
    if not os.path.exists(STUDENT_FILE):
        srsly.write_json({"101": {"original_answer": "Student Ans1", "structure": {"p1": "Part 1"}, "full_similarity_score": 0.8}}, STUDENT_FILE)
        
    OUTPUT_FILE = "data/prodigy_tasks_unified.jsonl"
    
    # --- Run the main process ---
    main(
        answer_key_path=ANSWER_KEY_FILE,
        student_answer_path=STUDENT_FILE,
        output_path=OUTPUT_FILE
    )