from database.models import Task
from datetime import datetime

def insert_tasks_to_db_direct(tasks, session):
    """
    Insert tasks into the database using SQLAlchemy ORM.

    Args:
        tasks (list): List of task dictionaries with nested subtasks
        session: SQLAlchemy session

    Returns:
        list: List of top-level task IDs that were created
    """
    top_level_task_ids = []

    def insert_task(task, parent_task_id=None):
        # Create a Task instance using SQLAlchemy ORM
        task_obj = Task(
            title=task["title"],
            description=task["description"],
            deadline=task.get("deadline"),
            priority=task.get("priority", "Medium"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            # status and created_at/updated_at will use default or be set by DB
            portfolio_id=task.get("portfolio_id"),
            # parent_task_id is not in your model, add if needed
        )
        # If your Task model has parent_task_id, set it here
        if hasattr(task_obj, "parent_task_id"):
            setattr(task_obj, "parent_task_id", parent_task_id)

        session.add(task_obj)
        session.flush()  # Flush to get the task_id

        # If this is a top-level task, add to our return list
        if parent_task_id is None:
            top_level_task_ids.append(task_obj.task_id)

        # Process subtasks recursively
        if "subtasks" in task and isinstance(task["subtasks"], list):
            for subtask in task["subtasks"]:
                insert_task(subtask, task_obj.task_id)

        return task_obj.task_id

    try:
        # Process all top-level tasks
        for task in tasks:
            insert_task(task)

        # Commit the transaction
        session.commit()
        return top_level_task_ids

    except Exception as e:
        # Rollback in case of error
        session.rollback()
        print(f"Error inserting tasks: {e}")
        return []


def get_task_with_subtasks(task_id, supabase_client):
    """Get task and all its subtasks"""
    # Get main task
    response = supabase_client.table("tasks").select("*").eq("task_id", task_id).execute()
    if not response.data:
        return None

    task = response.data[0]

    # Get all subtasks
    subtasks_response = (
        supabase_client.table("tasks").select("*").eq("parent_task_id", task_id).execute()
    )

    # Add subtasks to main task
    task["subtasks"] = subtasks_response.data

    # Recursively get subtasks of each subtask
    for subtask in task["subtasks"]:
        subtask_children = get_task_with_subtasks(subtask["task_id"], supabase_client)
        if subtask_children and "subtasks" in subtask_children:
            subtask["subtasks"] = subtask_children["subtasks"]

    return task
