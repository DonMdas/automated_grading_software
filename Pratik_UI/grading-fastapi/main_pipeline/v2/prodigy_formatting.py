import json
import srsly
import os

def stringify_structure(value):
    """
    Recursively converts non-string structure values into a single coherent string.
    """
    if isinstance(value, str):
        return value.strip().replace('"', '')
    if isinstance(value, list):
        return " ".join([stringify_structure(item) for item in value])
    if isinstance(value, dict):
        if 'content' in value:
            return stringify_structure(value['content'])
        return " ".join([stringify_structure(v) for v in value.values()])
    return str(value)

def create_constructed_task(q_id, question, structure_dict, original_answer, other_meta={}, scores_dict=None, requires_llm_evaluation=None):
    """
    A central function to build a Prodigy task by constructing text from a structure dictionary.
    It now accepts an optional scores_dict to format labels with scores and requires_llm_evaluation list.
    """
    separator = "\n\n"
    constructed_parts = []
    annotated_spans = []
    formatted_labels = []
    current_offset = 0
    requires_llm_evaluation = requires_llm_evaluation or []

    for original_label, structure_value in structure_dict.items():
        part_text = stringify_structure(structure_value)
        if not part_text:
            continue
            
        # Format the label with its score and evaluation method
        final_label = original_label
        if scores_dict and original_label in scores_dict:
            score = scores_dict[original_label]
            eval_method = "LLM" if original_label in requires_llm_evaluation else "Cosine"
            final_label = f"{original_label} ({score:.2f}) [{eval_method}]"
        elif original_label in requires_llm_evaluation:
            final_label = f"{original_label} [LLM]"
        
        formatted_labels.append(final_label)

        constructed_parts.append(part_text)
        
        start = current_offset
        end = start + len(part_text)
        
        annotated_spans.append({
            "start": start,
            "end": end,
            "label": final_label,
            "source": "constructed_v2"
        })
        
        current_offset = end + len(separator)

    final_text = separator.join(constructed_parts)
    
    meta_data = {
        "id": q_id,
        "question": question,
        "original_answer": original_answer
    }
    meta_data.update(other_meta)

    return {
        "text": final_text,
        "spans": annotated_spans,
        "meta": meta_data,
        "config": {
            "labels": formatted_labels
        }
    }

def process_answer_key_file(filepath):
    """Processes the teacher's answer key file with the new format."""
    print(f"Processing answer key file: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tasks = []
    for q_id, content in data.items():
        if "answer" not in content or "structure" not in content:
            continue
        
        requires_llm_evaluation = content.get("requires_llm_evaluation", [])
        
        task = create_constructed_task(
            q_id=q_id,
            question=content.get("question", "N/A"),
            structure_dict=content["structure"],
            original_answer=content["answer"],
            requires_llm_evaluation=requires_llm_evaluation
        )
        tasks.append(task)
    print(f"-> Found and processed {len(tasks)} tasks from the answer key.")
    return tasks

def process_student_answers_file(filepath):
    """
    Processes a student's answers file with the new format including requires_llm_evaluation.
    """
    print(f"Processing student answers file: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tasks = []
    for q_id, content in data.items():
        if "original_answer" not in content or "structure" not in content:
            continue

        other_meta = {k: v for k, v in content.items() if k not in ["original_answer", "structure", "embedding"]}
        requires_llm_evaluation = content.get("requires_llm_evaluation", [])
        
        scores_dict = {}
        if "structure_similarity_scores" in content and content["structure"]:
            scores = content["structure_similarity_scores"]
            labels = list(content["structure"].keys())
            
            # Create a mapping from original label to score
            scores_dict = {label: score for label, score in zip(labels, scores)}
            
            # Remove the Component Scores list from metadata - it's now shown in labels
            other_meta.pop("structure_similarity_scores", None)

        task = create_constructed_task(
            q_id=q_id,
            question=content.get("question", f"Student Answer for Q#{q_id}"),
            structure_dict=content["structure"],
            original_answer=content["original_answer"],
            other_meta=other_meta,
            scores_dict=scores_dict,
            requires_llm_evaluation=requires_llm_evaluation
        )
        tasks.append(task)
    print(f"-> Found and processed {len(tasks)} tasks from student answers.")
    return tasks


def main(answer_key_path, student_answer_path, output_path):
    """Main function to process both files and generate a single .jsonl output."""
    answer_key_tasks = process_answer_key_file(answer_key_path)
    student_tasks = process_student_answers_file(student_answer_path)
    
    all_tasks = answer_key_tasks + student_tasks
    
    srsly.write_jsonl(output_path, all_tasks)
    print(f"\n✅ Success! Created '{output_path}' with a total of {len(all_tasks)} tasks.")
    print("You can now run this file in Prodigy.")


if __name__ == "__main__":
    # Ensure the data directory exists
    if not os.path.exists("data"):
        os.makedirs("data")
        
    # --- Define your file paths here ---
    # NOTE: These paths assume your script is in the project root and data is in a 'data' subfolder.
    # Replace these with your actual files.
    ANSWER_KEY_FILE = "data/answer_key_with_structure.json"
    STUDENT_FILE = "data/s1_processed.json"
    OUTPUT_FILE = "data/prodigy_tasks_unified_with_scores.jsonl"
    
    # --- Run the main process ---
    # You would uncomment this block and run the script
    # For now, this is just a demonstration.
    # main(
    #     answer_key_path=ANSWER_KEY_FILE,
    #     student_answer_path=STUDENT_FILE,
    #     output_path=OUTPUT_FILE
    # )
    print("Script is ready. Update file paths in the `if __name__ == '__main__':` block and run.")