def insert_tasks_to_supabase(tasks, supabase_client):
    """
    Insert nested tasks into Supabase database
    
    Args:
        tasks: Nested task list
        supabase_client: Supabase client instance
    
    Returns:
        List of top-level task IDs
    """
    top_level_task_ids = []
    
    async def insert_task_with_subtasks(task, parent_task_id=None):
        # Prepare task data
        task_data = {
            'title': task['title'],
            'description': task['description'],
            'deadline': task.get('deadline'),
            'priority': task.get('priority', 'Medium'),
            'source_meeting_id': task.get('source_meeting_id'),
            'portfolio_id': task.get('portfolio_id'),
            'parent_task_id': parent_task_id
        }
        
        # Extract subtasks from task data
        subtasks = task.pop('subtasks', []) if 'subtasks' in task else []
        
        # Insert current task
        response = supabase_client.table('tasks').insert(task_data).execute()
        
        # Check response
        if 'error' in response and response['error']:
            raise Exception(f"Error inserting task: {response['error']}")
        
        # Get new inserted task ID
        task_id = response['data'][0]['task_id']
        
        # If it's a top-level task, record ID
        if parent_task_id is None:
            top_level_task_ids.append(task_id)
        
        # Recursively insert all subtasks
        for subtask in subtasks:
            await insert_task_with_subtasks(subtask, task_id)
        
        return task_id
    
    # Use async function to process all top-level tasks
    import asyncio
    
    async def process_all_tasks():
        for task in tasks:
            await insert_task_with_subtasks(task)
    
    # Run async function with better compatibility
    try:
        # Get the current event loop if one exists
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're in an existing event loop, use create_task
            future = asyncio.create_task(process_all_tasks())
            # Wait for it to complete
            loop.run_until_complete(future)
        else:
            # No running loop, safe to use run
            loop.run_until_complete(process_all_tasks())
    except RuntimeError:
        # No event loop in current context, create a new one
        asyncio.run(process_all_tasks())
    
    return top_level_task_ids

def insert_tasks_to_db_direct(tasks, connection):
    """
    Insert tasks into the database using a direct PostgreSQL connection.
    
    Args:
        tasks (list): List of task dictionaries with nested subtasks
        connection: PostgreSQL database connection
        
    Returns:
        list: List of top-level task IDs that were created
    """
    cursor = connection.cursor()
    top_level_task_ids = []
    
    def insert_task(task, parent_task_id=None):
        # Extract task data
        title = task['title']
        description = task['description']
        deadline = task.get('deadline')
        priority = task.get('priority', 'Medium')
        source_meeting_id = task.get('source_meeting_id')
        portfolio_id = task.get('portfolio_id')
        
        # Prepare SQL query
        sql = """
        INSERT INTO tasks (title, description, deadline, priority, source_meeting_id, portfolio_id, parent_task_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING task_id;
        """
        
        # Execute query
        cursor.execute(sql, (title, description, deadline, priority, source_meeting_id, portfolio_id, parent_task_id))
        task_id = cursor.fetchone()[0]
        
        # If this is a top-level task, add to our return list
        if parent_task_id is None:
            top_level_task_ids.append(task_id)
        
        # Process subtasks recursively
        if 'subtasks' in task and isinstance(task['subtasks'], list):
            for subtask in task['subtasks']:
                insert_task(subtask, task_id)
        
        return task_id
    
    try:
        # Process all top-level tasks
        for task in tasks:
            insert_task(task)
        
        # Commit the transaction
        connection.commit()
        return top_level_task_ids
    
    except Exception as e:
        # Rollback in case of error
        connection.rollback()
        print(f"Error inserting tasks: {e}")
        return []
    finally:
        # Close cursor
        cursor.close()

def get_task_with_subtasks(task_id, supabase_client):
    """Get task and all its subtasks"""
    # Get main task
    response = supabase_client.table('tasks').select('*').eq('task_id', task_id).execute()
    if not response.data:
        return None
    
    task = response.data[0]
    
    # Get all subtasks
    subtasks_response = supabase_client.table('tasks').select('*').eq('parent_task_id', task_id).execute()
    
    # Add subtasks to main task
    task['subtasks'] = subtasks_response.data
    
    # Recursively get subtasks of each subtask
    for subtask in task['subtasks']:
        subtask_children = get_task_with_subtasks(subtask['task_id'], supabase_client)
        if subtask_children and 'subtasks' in subtask_children:
            subtask['subtasks'] = subtask_children['subtasks']
    
    return task