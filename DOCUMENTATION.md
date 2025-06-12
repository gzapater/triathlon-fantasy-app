# Project Overview

This project is a backend system designed for managing race-related information. It is built using Flask, a Python web framework, and utilizes SQLAlchemy for database interactions.

The system supports key functionalities such as:
- **User Roles:** Manages different user roles (e.g., Administrator, League Admin, Player) with distinct permissions.
- **Race Creation and Management:** Allows authorized users to create and manage races. This includes defining race details like title, description, event date, location, and gender categories.
- **Race Formats:** Supports various race formats (e.g., Triathlon, Duathlon, Acuatlón), which can be associated with races.
- **Race Segments:** Enables the definition of segments within a race (e.g., Swimming, Cycling, Running, Transitions) along with their respective distances.
- **Race Questions:** Provides a system for creating and associating different types of questions (Free Text, Multiple Choice, Ordering) with specific races, including scoring logic for each type.

# Setup and Installation

These instructions will guide you through setting up the backend application locally for development.

## 1. Prerequisites
- Python 3.x
- pip (Python package installer)
- Git

## 2. Clone Repository
Clone the project repository to your local machine:
```bash
git clone <repository-url>
# Replace <repository-url> with the actual URL of the repository.
```

## 3. Navigate to Backend Directory
The main application code is typically within a `backend` directory.
```bash
cd path/to/repository/backend
# Adjust path/to/repository to where you cloned the project.
```

## 4. Create and Activate Virtual Environment
It's highly recommended to use a virtual environment to manage project dependencies.

- **Create the virtual environment** (usually in the project root or backend directory):
  ```bash
  python -m venv venv
  ```
- **Activate the virtual environment:**
    - On Linux/macOS:
      ```bash
      source venv/bin/activate
      ```
    - On Windows (Command Prompt/PowerShell):
      ```bash
      venv\Scripts\activate
      ```
  Your command prompt should now be prefixed with `(venv)`.

## 5. Install Dependencies
Install the required Python packages. Assuming a `requirements.txt` file is present in the current directory (`backend`):
```bash
pip install -r requirements.txt
```
*Note: If a `requirements.txt` is not provided or is located elsewhere (e.g., project root), adjust the command accordingly (e.g., `pip install -r ../requirements.txt`). Key dependencies include Flask, Flask-SQLAlchemy, Flask-Login, Flask-Migrate, bcrypt, and Werkzeug.*

## 6. Environment Variables
The application requires certain environment variables to be set for configuration.

- **`FLASK_SECRET_KEY`**: A secret key used by Flask for session management and cryptographic signing. This should be a long, random string.
- **`DATABASE_URL`**: The connection string for the database.

**Set these variables in your shell before running the application:**

- **For Linux/macOS:**
  ```bash
  export FLASK_SECRET_KEY='your_very_strong_and_unique_secret_key_here'
  export DATABASE_URL='postgresql://user:password@localhost:5432/your_database_name'
  ```
- **For Windows (PowerShell):**
  ```powershell
  $env:FLASK_SECRET_KEY = 'your_very_strong_and_unique_secret_key_here'
  $env:DATABASE_URL = 'postgresql://user:password@localhost:5432/your_database_name'
  ```

**Important:**
  - Replace placeholder values with your actual secret key and database credentials.
  - **For local development with SQLite:** You can use a file-based SQLite database. If `app.py` is in the `backend` directory, and you want the database in an `instance` folder at the project root:
    ```bash
    # Linux/macOS
    export DATABASE_URL='sqlite:///../instance/app_dev.db'
    # Windows PowerShell
    $env:DATABASE_URL = 'sqlite:///../instance/app_dev.db'
    ```
    Ensure the `instance` folder exists at the project root (`../instance/`) relative to the `backend` directory.

## 7. Database Migrations
The project uses Flask-Migrate to manage database schema changes. The `migrations` folder should be present in the `backend` directory.

- **Initialize Migrations (only if the `migrations` folder does not exist):**
  This step is typically already done if the `migrations` folder is part of the repository.
  ```bash
  flask db init
  ```
- **Create a New Migration (if you have changed SQLAlchemy models):**
  This command generates a new migration script based on changes detected in your models.
  ```bash
  flask db migrate -m "Descriptive message for migration (e.g., add_user_bio_field)"
  ```
- **Apply Migrations:**
  This command applies any pending migration scripts to your database, updating the schema. This is usually the main command needed after cloning and setting up, or after generating a new migration.
  ```bash
  flask db upgrade
  # or, using the management script:
  python backend/manage.py db upgrade
  ```
  *Note: `app.py` also contains `db.create_all()`, which can create tables. However, for structured schema management, Flask-Migrate commands (`flask db upgrade` or `python backend/manage.py db upgrade`) are preferred.*

## 7.1. Database Seeding (Initial Data)
After ensuring your database schema is up to date using the migration commands, you can populate the database with initial necessary data such as default roles, race formats, segments, and question types.

To seed the database, run the following command from the project's root directory (the one containing the `backend` folder):

```bash
python backend/manage.py seed_data
```

**Note:**
- Ensure that the `DATABASE_URL` environment variable is correctly set before running this command, as it needs to connect to your database. The `FLASK_SECRET_KEY` might also be required by the underlying Flask app initialization within `manage.py`.
- This command should typically be run once after the initial database setup and migrations (`flask db upgrade` or `python backend/manage.py db upgrade`).

## 8. Run the Application
Once the setup is complete, you can run the Flask development server from the `backend` directory.
```bash
python app.py
```
Alternatively, using the `flask` CLI (ensure `FLASK_APP=app.py` is set or understood by Flask's auto-discovery):
```bash
flask run
```
The application will typically be available at `http://127.0.0.1:5000/`.

---
*Disclaimer: These are general setup instructions. Depending on the specific state of the repository and your local environment, minor adjustments might be necessary.*

# API Endpoints

This section details the available API endpoints for interacting with the backend system.

## 1. Get Race Formats
- **Method & Path:** `GET /api/race-formats`
- **Description:** Retrieves a list of all available race formats.
- **Authentication/Authorization:** None.
- **Request Parameters:** None.
- **Responses:**
    - **Success (200 OK):**
      ```json
      [
        {"id": 1, "name": "Triatlón"},
        {"id": 2, "name": "Duatlón"}
        // ... more formats
      ]
      ```
    - **Error (500 Internal Server Error):**
      ```json
      {"message": "Error fetching race formats"}
      ```

## 2. Create Race
- **Method & Path:** `POST /api/races`
- **Description:** Creates a new race event.
- **Authentication/Authorization:** Login required. User role must be 'LEAGUE_ADMIN' or 'ADMIN'.
- **Request Parameters (JSON Body):**
    - `title` (String, required): The title of the race.
    - `description` (String, optional): A description of the race.
    - `race_format_id` (Integer, required): The ID of the race format (obtained from `GET /api/race-formats`).
    - `event_date` (String, required): The date of the event in 'YYYY-MM-DD' format.
    - `location` (String, optional): The location of the race.
    - `promo_image_url` (String, optional): URL for a promotional image.
    - `gender_category` (String, required): Gender category for the race (e.g., "Masculino", "Femenino", "Ambos").
    - `segments` (Array of Objects, required): A list of segments for the race. Each object:
        - `segment_id` (Integer, required): The ID of the segment.
        - `distance_km` (Float/Integer, required): The distance of the segment in kilometers (must be non-negative; positive for non-transition segments).
- **Responses:**
    - **Success (201 Created):**
      ```json
      {"message": "Race created successfully", "race_id": <new_race_id>}
      ```
    - **Error (400 Bad Request):** For invalid input (e.g., no data, missing fields, incorrect types, invalid IDs). Example messages:
        - `{"message": "Invalid input: No data provided"}`
        - `{"message": "Missing required fields: title, race_format_id"}`
        - `{"message": "Title must be a non-empty string."}`
        - `{"message": "Invalid race_format_id: X does not exist."}`
        - `{"message": "Segments must be a non-empty list."}`
    - **Error (403 Forbidden):** If the user does not have 'LEAGUE_ADMIN' or 'ADMIN' role.
      ```json
      {"message": "Forbidden: You do not have permission to create races."}
      ```
    - **Error (500 Internal Server Error):**
      ```json
      {"message": "Error creating race"}
      ```

## 3. Get Race Questions
- **Method & Path:** `GET /api/races/<int:race_id>/questions`
- **Description:** Retrieves all questions associated with a specific race, ordered by question ID.
- **Authentication/Authorization:** Login required.
- **Request Parameters:**
    - **Path Parameters:**
        - `race_id` (Integer): The ID of the race.
- **Responses:**
    - **Success (200 OK):** An array of question objects. The `_serialize_question` helper function determines the exact structure.
      ```json
      [
        {
          "id": <question_id>,
          "text": "<question_text>",
          "question_type": "<type_name>", // "FREE_TEXT", "MULTIPLE_CHOICE", or "ORDERING"
          "is_active": <boolean>,
          "race_id": <race_id_of_this_question>,
          // Type-specific scoring fields (nullable if not applicable):
          "max_score_free_text": <integer_value_or_null>,
          "is_mc_multiple_correct": <boolean_or_null>,
          "points_per_correct_mc": <integer_value_or_null>,
          "points_per_incorrect_mc": <integer_value_or_null>,
          "total_score_mc_single": <integer_value_or_null>,
          "points_per_correct_order": <integer_value_or_null>,
          "bonus_for_full_order": <integer_value_or_null>,
          "options": [ // Options are ordered by their ID
            {
              "id": <option_id>,
              "option_text": "<text>",
              "is_correct_mc_single": <boolean_or_null>,
              "is_correct_mc_multiple": <boolean_or_null>,
              "correct_order_index": <integer_value_or_null>
            }
            // ... more options
          ]
        }
        // ... more questions
      ]
      ```
    - **Error (404 Not Found):** If the specified `race_id` does not exist.
      ```json
      {"message": "Race not found"}
      ```

## 4. Create Free Text Question
- **Method & Path:** `POST /api/races/<int:race_id>/questions/free-text`
- **Description:** Creates a new free text question for a specific race.
- **Authentication/Authorization:** Login required. User role must be 'ADMIN' or 'LEAGUE_ADMIN'.
- **Request Parameters:**
    - **Path Parameters:**
        - `race_id` (Integer): The ID of the race.
    - **JSON Body:**
        - `text` (String, required): The text of the question.
        - `max_score_free_text` (Integer, required): Maximum score (must be positive).
        - `is_active` (Boolean, optional, default: `true`): Whether the question is active.
- **Responses:**
    - **Success (201 Created):** Returns the created question object (serialized).
      ```json
      {
        "id": <new_question_id>,
        "text": "<question_text>",
        "question_type": "FREE_TEXT",
        "is_active": <boolean>,
        "race_id": <race_id>,
        "max_score_free_text": <integer_value>,
        "options": [] // Free text questions don't have options
        // ... other fields from serialization will be null or default
      }
      ```
    - **Error (400 Bad Request):** For invalid input (e.g., no data, missing text, invalid score).
        - `{"message": "Invalid input: No data provided"}`
        - `{"message": "Question text is required and must be a non-empty string"}`
        - `{"message": "max_score_free_text is required and must be a positive integer"}`
    - **Error (403 Forbidden):** `{"message": "Forbidden: Insufficient permissions"}`
    - **Error (404 Not Found):** `{"message": "Race not found"}`
    - **Error (500 Internal Server Error):**
        - `{"message": "QuestionType 'FREE_TEXT' not found. Please seed database."}`
        - `{"message": "Error creating question"}`

## 5. Update Free Text Question
- **Method & Path:** `PUT /api/questions/free-text/<int:question_id>`
- **Description:** Updates an existing free text question.
- **Authentication/Authorization:** Login required. User role must be 'ADMIN' or 'LEAGUE_ADMIN'.
- **Request Parameters:**
    - **Path Parameters:**
        - `question_id` (Integer): The ID of the question to update.
    - **JSON Body (all fields optional):**
        - `text` (String): New text for the question (must be non-empty if provided).
        - `max_score_free_text` (Integer): New maximum score (must be positive if provided).
        - `is_active` (Boolean): New active status.
- **Responses:**
    - **Success (200 OK):** Returns the updated question object (serialized).
    - **Error (400 Bad Request):** For invalid input or if not a 'FREE_TEXT' question.
        - `{"message": "Invalid input: No data provided"}`
        - `{"message": "Cannot update non-FREE_TEXT question via this endpoint"}`
        - `{"message": "Question text must be a non-empty string if provided"}`
        - `{"message": "max_score_free_text must be a positive integer if provided"}`
        - `{"message": "is_active must be a boolean if provided"}`
    - **Error (403 Forbidden):** `{"message": "Forbidden: Insufficient permissions"}`
    - **Error (404 Not Found):** `{"message": "Question not found"}`
    - **Error (500 Internal Server Error):** `{"message": "Error updating question"}`

## 6. Delete Question
- **Method & Path:** `DELETE /api/questions/<int:question_id>`
- **Description:** Deletes a question of any type (and its associated options if any).
- **Authentication/Authorization:** Login required. User role must be 'ADMIN' or 'LEAGUE_ADMIN'.
- **Request Parameters:**
    - **Path Parameters:**
        - `question_id` (Integer): The ID of the question to delete.
- **Responses:**
    - **Success (200 OK or 204 No Content):**
      ```json
      {"message": "Question deleted successfully"}
      ```
    - **Error (403 Forbidden):** `{"message": "Forbidden: Insufficient permissions"}`
    - **Error (404 Not Found):** `{"message": "Question not found"}`
    - **Error (500 Internal Server Error):** `{"message": "Error deleting question"}`

## 7. Hello (Protected Test Endpoint)
- **Method & Path:** `GET /api/hello`
- **Description:** A simple protected endpoint to verify user authentication status.
- **Authentication/Authorization:** Login required.
- **Request Parameters:** None.
- **Responses:**
    - **Success (200 OK):**
      ```json
      {"message": "Hello <username>, this is a protected message from Backend!"}
      ```

## 8. Register User
- **Method & Path:** `POST /api/register`
- **Description:** Registers a new user in the system.
- **Authentication/Authorization:** None.
- **Request Parameters (JSON Body):**
    - `name` (String, required): Full name of the user.
    - `username` (String, required): Desired username (must be unique).
    - `email` (String, required): User's email address (must be unique).
    - `password` (String, required): User's password.
    - `role` (String, required): Role code for the user (e.g., 'PLAYER', 'LEAGUE_ADMIN', 'ADMIN'). Must match a `code` in the `roles` table.
- **Responses:**
    - **Success (201 Created):**
      ```json
      {"message": "User registered successfully"}
      ```
    - **Error (400 Bad Request):**
        - `{"message": "Invalid input: No data provided"}`
        - `{"message": "Missing required fields"}`
        - `{"message": "Invalid role code: '<role_code>' specified. Available role codes are typically 'PLAYER', 'LEAGUE_ADMIN', 'ADMIN'."}`
    - **Error (409 Conflict):**
        - `{"message": "Username already exists"}`
        - `{"message": "Email already exists"}`
    - **Error (500 Internal Server Error):**
      ```json
      {"message": "Registration failed due to a server error"}
      ```

## 9. Login User
- **Method & Path:** `POST /api/login`
- **Description:** Authenticates an existing user and establishes a session.
- **Authentication/Authorization:** None.
- **Request Parameters (JSON Body):**
    - `username` (String, required): User's username.
    - `password` (String, required): User's password.
- **Responses:**
    - **Success (200 OK):** Sets a session cookie.
      ```json
      {"message": "Login successful", "user_id": <user_id>, "username": "<username>"}
      ```
    - **Error (400 Bad Request):**
        - `{"message": "Invalid input: No data provided"}`
        - `{"message": "Username and password are required"}`
    - **Error (401 Unauthorized):** If username/password is incorrect.
      ```json
      {"message": "Invalid username or password"}
      ```
    - **Error (403 Forbidden):** If the user account is inactive/disabled.
      ```json
      {"message": "Account disabled. Please contact support."}
      ```

## 10. Logout User
- **Method & Path:** `POST /api/logout`
- **Description:** Logs out the currently authenticated user, clearing their session.
- **Authentication/Authorization:** Login required.
- **Request Parameters:** None.
- **Responses:**
    - **Success (200 OK):**
      ```json
      {"message": "Logout successful"}
      ```

## 11. Create Multiple Choice Question
- **Method & Path:** `POST /api/races/<int:race_id>/questions/multiple-choice`
- **Description:** Creates a new multiple choice question for a specific race.
- **Authentication/Authorization:** Login required. User role must be 'ADMIN' or 'LEAGUE_ADMIN'.
- **Request Parameters:**
    - **Path Parameters:**
        - `race_id` (Integer): The ID of the race.
    - **JSON Body:**
        - `text` (String, required): The text of the question.
        - `is_mc_multiple_correct` (Boolean, required): `true` for multiple correct answers (checkboxes), `false` for a single correct answer (radio buttons).
        - `options` (Array of Objects, required, min 2 items): List of choices. Each object:
            - `option_text` (String, required): Text for the option.
            - `is_correct` (Boolean, required): Whether this option is correct. (For single-correct, only one option should have this as true).
        - `points_per_correct_mc` (Integer, required if `is_mc_multiple_correct` is `true`): Points for each correct selection.
        - `points_per_incorrect_mc` (Integer, optional, default: 0, if `is_mc_multiple_correct` is `true`): Points for each incorrect selection (can be negative).
        - `total_score_mc_single` (Integer, required and positive if `is_mc_multiple_correct` is `false`): Total points if the single correct option is chosen.
        - `is_active` (Boolean, optional, default: `true`): Whether the question is active.
- **Responses:**
    - **Success (201 Created):** Returns the created question object (serialized).
    - **Error (400 Bad Request):** For invalid input (e.g., missing fields, incorrect option structure, inconsistent `is_correct` for single-choice).
        - `{"message": "Question text is required and must be a non-empty string"}`
        - `{"message": "is_mc_multiple_correct (boolean) is required"}`
        - `{"message": "At least two options are required for a multiple choice question"}`
        - `{"message": "Each option must have 'option_text' (string) and 'is_correct' (boolean)"}`
        - `{"message": "For single-correct multiple choice, exactly one option must be marked as correct"}`
        - `{"message": "points_per_correct_mc is required and must be an integer for multiple-correct MCQs"}`
        - `{"message": "total_score_mc_single is required and must be a positive integer for single-correct MCQs"}`
    - **Error (403 Forbidden):** `{"message": "Forbidden: Insufficient permissions"}`
    - **Error (404 Not Found):** `{"message": "Race not found"}`
    - **Error (500 Internal Server Error):**
        - `{"message": "QuestionType 'MULTIPLE_CHOICE' not found. Please seed database."}`
        - `{"message": "Error creating question"}`

## 12. Update Multiple Choice Question
- **Method & Path:** `PUT /api/questions/multiple-choice/<int:question_id>`
- **Description:** Updates an existing multiple choice question, including its options and scoring.
- **Authentication/Authorization:** Login required. User role must be 'ADMIN' or 'LEAGUE_ADMIN'.
- **Request Parameters:**
    - **Path Parameters:**
        - `question_id` (Integer): The ID of the question to update.
    - **JSON Body (all fields optional, provide only fields to be updated):**
        - `text` (String): New question text.
        - `is_active` (Boolean): New active status.
        - `is_mc_multiple_correct` (Boolean): Change the type of MC question. If changed, related scoring fields might become required or reset.
        - `points_per_correct_mc` (Integer), `points_per_incorrect_mc` (Integer), `total_score_mc_single` (Integer): Update scoring fields. Ensure they are consistent with `is_mc_multiple_correct`.
        - `options` (Array of Objects): If provided, **replaces all existing options**. Structure same as in POST.
- **Responses:**
    - **Success (200 OK):** Returns the updated question object (serialized).
    - **Error (400 Bad Request):** For invalid input or if not a 'MULTIPLE_CHOICE' question.
        - `{"message": "Cannot update non-MULTIPLE_CHOICE question via this endpoint"}`
        - Other messages similar to POST for validation.
    - **Error (403 Forbidden):** `{"message": "Forbidden: Insufficient permissions"}`
    - **Error (404 Not Found):** `{"message": "Question not found"}`
    - **Error (500 Internal Server Error):** `{"message": "Error updating question"}`

## 13. Create Ordering Question
- **Method & Path:** `POST /api/races/<int:race_id>/questions/ordering`
- **Description:** Creates a new ordering question for a specific race. The order of options in the request defines the correct order.
- **Authentication/Authorization:** Login required. User role must be 'ADMIN' or 'LEAGUE_ADMIN'.
- **Request Parameters:**
    - **Path Parameters:**
        - `race_id` (Integer): The ID of the race.
    - **JSON Body:**
        - `text` (String, required): The question text.
        - `points_per_correct_order` (Integer, required, positive): Points awarded for each item correctly placed in the sequence.
        - `bonus_for_full_order` (Integer, optional, non-negative, default: 0): Additional points if all items are in the correct order.
        - `options` (Array of Objects, required, min 2 items): Items to be ordered. The order in this array defines the correct sequence. Each object:
            - `option_text` (String, required): Text of the item.
        - `is_active` (Boolean, optional, default: `true`): Whether the question is active.
- **Responses:**
    - **Success (201 Created):** Returns the created question object (serialized). `correct_order_index` for options will be set based on input order.
    - **Error (400 Bad Request):** For invalid input (e.g., missing fields, insufficient options).
        - `{"message": "Question text is required and must be a non-empty string"}`
        - `{"message": "points_per_correct_order is required and must be a positive integer"}`
        - `{"message": "bonus_for_full_order must be a non-negative integer"}`
        - `{"message": "At least two options (items to order) are required"}`
        - `{"message": "Each option must have 'option_text' (string)"}`
    - **Error (403 Forbidden):** `{"message": "Forbidden: Insufficient permissions"}`
    - **Error (404 Not Found):** `{"message": "Race not found"}`
    - **Error (500 Internal Server Error):**
        - `{"message": "QuestionType 'ORDERING' not found. Please seed database."}`
        - `{"message": "Error creating ordering question"}`

## 14. Update Ordering Question
- **Method & Path:** `PUT /api/questions/ordering/<int:question_id>`
- **Description:** Updates an existing ordering question.
- **Authentication/Authorization:** Login required. User role must be 'ADMIN' or 'LEAGUE_ADMIN'.
- **Request Parameters:**
    - **Path Parameters:**
        - `question_id` (Integer): The ID of the question to update.
    - **JSON Body (all fields optional, provide only fields to be updated):**
        - `text` (String): New question text.
        - `points_per_correct_order` (Integer, positive): New points per correct item.
        - `bonus_for_full_order` (Integer, non-negative): New bonus for full correct order.
        - `is_active` (Boolean): New active status.
        - `options` (Array of Objects): If provided, **replaces all existing options**. Order defines new correct sequence. Each object: `option_text` (String).
- **Responses:**
    - **Success (200 OK):** Returns the updated question object (serialized).
    - **Error (400 Bad Request):** For invalid input or if not an 'ORDERING' question.
        - `{"message": "Cannot update non-ORDERING question via this endpoint"}`
        - Other messages similar to POST for validation.
    - **Error (403 Forbidden):** `{"message": "Forbidden: Insufficient permissions"}`
    - **Error (404 Not Found):** `{"message": "Question not found"}`
    - **Error (500 Internal Server Error):** `{"message": "Error updating ordering question"}`

## 15. Get Current User Details
- **Method & Path:** `GET /api/user/me`
- **Description:** Retrieves details (username and role description) of the currently authenticated user.
- **Authentication/Authorization:** Login required.
- **Request Parameters:** None.
- **Responses:**
    - **Success (200 OK):**
      ```json
      {
        "username": "<current_user_username>",
        "role": "<current_user_role_description>" // e.g., "Administrador", "League Admin"
      }
      ```

## 16. Get General Admin Data (Role-Protected)
- **Method & Path:** `GET /api/admin/general_data`
- **Description:** Example endpoint to retrieve data intended only for users with the 'ADMIN' role.
- **Authentication/Authorization:** Login required. User role must be 'ADMIN'.
- **Request Parameters:** None.
- **Responses:**
    - **Success (200 OK):**
      ```json
      {"message": "Data for General Admin"}
      ```
    - **Error (403 Forbidden):** If user is not 'ADMIN'.
      ```json
      {"message": "Forbidden: You do not have the required permissions."}
      ```

## 17. Get League Admin Data (Role-Protected)
- **Method & Path:** `GET /api/admin/league_data`
- **Description:** Example endpoint to retrieve data intended for users with 'LEAGUE_ADMIN' or 'ADMIN' roles.
- **Authentication/Authorization:** Login required. User role must be 'LEAGUE_ADMIN' or 'ADMIN'.
- **Request Parameters:** None.
- **Responses:**
    - **Success (200 OK):**
      ```json
      {"message": "Data for League Admin (accessible by League and General Admins)"}
      ```
    - **Error (403 Forbidden):** If user is not 'LEAGUE_ADMIN' or 'ADMIN'.
      ```json
      {"message": "Forbidden: You do not have the required permissions."}
      ```

## 18. Get User Personal Data (Role-Protected)
- **Method & Path:** `GET /api/user/personal_data`
- **Description:** Example endpoint to retrieve data intended only for users with the 'PLAYER' role.
- **Authentication/Authorization:** Login required. User role must be 'PLAYER'.
- **Request Parameters:** None.
- **Responses:**
    - **Success (200 OK):**
      ```json
      {"message": "Data for User role"}
      ```
    - **Error (403 Forbidden):** If user is not 'PLAYER'.
      ```json
      {"message": "Forbidden: You do not have the required permissions for this data."}
      ```

# Database Models

This section describes the SQLAlchemy database models used in the application, detailing their fields and relationships.

## 1. Role
- **Description:** Represents user roles within the system, defining levels of access and permissions (e.g., Administrator, League Admin, Player).
- **Table Name:** `roles`
- **Fields:**
    - `id`: Integer, Primary Key.
    - `code`: String(80), Unique, Not Nullable. (e.g., 'ADMIN', 'LEAGUE_ADMIN', 'PLAYER')
    - `description`: String(255), Not Nullable. (e.g., 'Administrator', 'League Admin', 'Player')
- **Relationships:**
    - `users` (One-to-Many with `User`):
        - **Type:** A `Role` can be associated with many `User` instances.
        - **Backref:** `role` (A `User` instance will have a `role` attribute to access its `Role` object).
        - **Laziness:** `lazy=True` (The related `User` objects are loaded from the database when the `users` attribute is first accessed).

## 2. User
- **Description:** Represents application users, including authentication details and role assignment. Inherits from `UserMixin` for Flask-Login compatibility.
- **Table Name:** `users`
- **Fields:**
    - `id`: Integer, Primary Key.
    - `name`: String(100), Not Nullable.
    - `username`: String(80), Unique, Not Nullable.
    - `email`: String(120), Unique, Not Nullable.
    - `password_hash`: String(128), Not Nullable (Stores bcrypt-hashed password).
    - `role_id`: Integer, Foreign Key to `roles.id`, Not Nullable.
    - `is_active`: Boolean, Default: `True`, Not Nullable (Allows deactivating accounts without deleting).
    - `is_deleted`: Boolean, Default: `False`, Not Nullable (For soft-delete functionality).
    - `created_at`: DateTime, Default: `datetime.utcnow`, Not Nullable.
    - `updated_at`: DateTime, Default: `datetime.utcnow`, On Update: `datetime.utcnow`, Not Nullable.
- **Relationships:**
    - `role` (Many-to-One with `Role`):
        - **Type:** A `User` has one `Role`.
        - **Foreign Key:** `role_id` references `roles.id`.
        - **Backref:** `users` (A `Role` instance will have a `users` attribute to access its list of `User` objects).
        - **Laziness:** `lazy=True`.
    - `races` (One-to-Many with `Race`):
        - **Type:** A `User` can create/own many `Race` instances.
        - **Backref:** `user` (A `Race` instance will have a `user` attribute to access its owner `User` object).
        - **Laziness:** `lazy=True`.

## 3. RaceFormat
- **Description:** Defines the type or format of a race (e.g., Triathlon, Duathlon, Acuatlón).
- **Table Name:** `race_formats`
- **Fields:**
    - `id`: Integer, Primary Key.
    - `name`: String(255), Unique, Not Nullable.
- **Relationships:**
    - `races` (One-to-Many with `Race`):
        - **Type:** A `RaceFormat` can be associated with many `Race` instances.
        - **Backref:** `race_format` (A `Race` instance will have a `race_format` attribute).
        - **Laziness:** `lazy=True`.

## 4. Segment
- **Description:** Defines a standard segment or leg of a race (e.g., Swimming, Cycling, Running, Transition 1).
- **Table Name:** `segments`
- **Fields:**
    - `id`: Integer, Primary Key.
    - `name`: String(255), Unique, Not Nullable.
- **Relationships:**
    - `race_details` (One-to-Many with `RaceSegmentDetail`):
        - **Type:** A `Segment` can be part of many `RaceSegmentDetail` entries.
        - **Backref:** `segment` (A `RaceSegmentDetail` instance will have a `segment` attribute).
        - **Laziness:** `lazy=True`.

## 5. Race
- **Description:** Represents a specific race event, including its details, format, segments, and associated questions.
- **Table Name:** `races`
- **Fields:**
    - `id`: Integer, Primary Key.
    - `title`: String(255), Not Nullable.
    - `description`: Text, Nullable.
    - `race_format_id`: Integer, Foreign Key to `race_formats.id`, Not Nullable.
    - `event_date`: DateTime, Not Nullable.
    - `location`: String(255), Nullable.
    - `promo_image_url`: String(255), Nullable.
    - `category`: String(255), Default: "Elite", Not Nullable.
    - `gender_category`: String(255), Not Nullable (e.g., "Masculino", "Femenino", "Ambos").
    - `user_id`: Integer, Foreign Key to `users.id`, Not Nullable (identifies the creator/owner).
    - `created_at`: DateTime, Default: `datetime.utcnow`, Not Nullable.
    - `updated_at`: DateTime, Default: `datetime.utcnow`, On Update: `datetime.utcnow`, Not Nullable.
- **Relationships:**
    - `race_format` (Many-to-One with `RaceFormat`):
        - **Type:** A `Race` has one `RaceFormat`.
        - **Foreign Key:** `race_format_id` references `race_formats.id`.
        - **Backref:** `races`.
        - **Laziness:** `lazy=True`.
    - `user` (Many-to-One with `User`):
        - **Type:** A `Race` is created by one `User`.
        - **Foreign Key:** `user_id` references `users.id`.
        - **Backref:** `races`.
        - **Laziness:** `lazy=True`.
    - `segment_details` (One-to-Many with `RaceSegmentDetail`):
        - **Type:** A `Race` can have many `RaceSegmentDetail` entries defining its structure.
        - **Backref:** `race`.
        - **Laziness:** `lazy=True`.
    - `questions` (One-to-Many with `Question`):
        - **Type:** A `Race` can have many associated `Question` instances.
        - **Backref:** `race`.
        - **Laziness:** `lazy='dynamic'` (Allows for further querying on the `questions` collection before loading).

## 6. RaceSegmentDetail
- **Description:** An association table linking a `Race` to a `Segment` and specifying the distance for that segment within that particular race.
- **Table Name:** `race_segment_details`
- **Fields:**
    - `id`: Integer, Primary Key.
    - `race_id`: Integer, Foreign Key to `races.id`, Not Nullable.
    - `segment_id`: Integer, Foreign Key to `segments.id`, Not Nullable.
    - `distance_km`: Float, Not Nullable (Distance in kilometers).
- **Relationships:**
    - `race` (Many-to-One with `Race`):
        - **Type:** A `RaceSegmentDetail` belongs to one `Race`.
        - **Foreign Key:** `race_id` references `races.id`.
        - **Backref:** `segment_details`.
        - **Laziness:** `lazy=True`.
    - `segment` (Many-to-One with `Segment`):
        - **Type:** A `RaceSegmentDetail` refers to one `Segment` definition.
        - **Foreign Key:** `segment_id` references `segments.id`.
        - **Backref:** `race_details`.
        - **Laziness:** `lazy=True`.

## 7. QuestionType
- **Description:** Defines the type of a question (e.g., 'FREE_TEXT', 'MULTIPLE_CHOICE', 'ORDERING').
- **Table Name:** `question_types`
- **Fields:**
    - `id`: Integer, Primary Key.
    - `name`: String(100), Unique, Not Nullable.
- **Relationships:**
    - `questions` (One-to-Many with `Question`):
        - **Type:** A `QuestionType` can be associated with many `Question` instances.
        - **Backref:** `question_type`.
        - **Laziness:** `lazy=True`.

## 8. Question
- **Description:** Represents a question associated with a specific race, including its type, text, active status, and scoring parameters.
- **Table Name:** `questions`
- **Fields:**
    - `id`: Integer, Primary Key.
    - `race_id`: Integer, Foreign Key to `races.id`, Not Nullable.
    - `question_type_id`: Integer, Foreign Key to `question_types.id`, Not Nullable.
    - `text`: Text, Not Nullable (The actual content of the question).
    - `is_active`: Boolean, Default: `True`, Not Nullable.
    - `created_at`: DateTime, Default: `datetime.utcnow`, Not Nullable.
    - `updated_at`: DateTime, Default: `datetime.utcnow`, On Update: `datetime.utcnow`, Not Nullable.
    - **Scoring Fields (nullable, type-dependent):**
        - `max_score_free_text`: Integer, Nullable (For 'FREE_TEXT' type).
        - `is_mc_multiple_correct`: Boolean, Nullable (For 'MULTIPLE_CHOICE', `True` for multiple-answer, `False` for single-answer).
        - `points_per_correct_mc`: Integer, Nullable (For 'MULTIPLE_CHOICE' with multiple answers).
        - `points_per_incorrect_mc`: Integer, Nullable (For 'MULTIPLE_CHOICE' with multiple answers, can be negative).
        - `total_score_mc_single`: Integer, Nullable (For 'MULTIPLE_CHOICE' with a single answer).
        - `points_per_correct_order`: Integer, Nullable (For 'ORDERING' type).
        - `bonus_for_full_order`: Integer, Nullable (For 'ORDERING' type).
- **Relationships:**
    - `race` (Many-to-One with `Race`):
        - **Type:** A `Question` belongs to one `Race`.
        - **Foreign Key:** `race_id` references `races.id`.
        - **Backref:** `questions`.
        - **Laziness:** `lazy='dynamic'`.
    - `question_type` (Many-to-One with `QuestionType`):
        - **Type:** A `Question` has one `QuestionType`.
        - **Foreign Key:** `question_type_id` references `question_types.id`.
        - **Backref:** `questions`.
        - **Laziness:** `lazy=True`.
    - `options` (One-to-Many with `QuestionOption`):
        - **Type:** A `Question` can have many `QuestionOption` instances.
        - **Backref:** `question`.
        - **Laziness:** `lazy='dynamic'`.
        - **Cascade:** `all, delete-orphan` (If a Question is deleted, its options are also deleted).

## 9. QuestionOption
- **Description:** Represents a specific choice or item for a `Question`. Used for 'MULTIPLE_CHOICE' and 'ORDERING' question types.
- **Table Name:** `question_options`
- **Fields:**
    - `id`: Integer, Primary Key.
    - `question_id`: Integer, Foreign Key to `questions.id`, Not Nullable.
    - `option_text`: String(500), Not Nullable (The text displayed for this option).
    - `is_correct_mc_single`: Boolean, Default: `False`, Nullable (For single-answer 'MULTIPLE_CHOICE' questions).
    - `is_correct_mc_multiple`: Boolean, Default: `False`, Nullable (For multiple-answer 'MULTIPLE_CHOICE' questions).
    - `correct_order_index`: Integer, Nullable (For 'ORDERING' questions, indicates the correct position in the sequence, 0-indexed).
    - `created_at`: DateTime, Default: `datetime.utcnow`, Not Nullable.
    - `updated_at`: DateTime, Default: `datetime.utcnow`, On Update: `datetime.utcnow`, Not Nullable.
- **Relationships:**
    - `question` (Many-to-One with `Question`):
        - **Type:** A `QuestionOption` belongs to one `Question`.
        - **Foreign Key:** `question_id` references `questions.id`.
        - **Backref:** `options`.
        - **Laziness:** `lazy='dynamic'`.
        - **Cascade:** `all, delete-orphan` (Implicitly handled via the relationship on `Question.options` if not redefined here, but good to be aware).The `DOCUMENTATION.md` has been thoroughly reviewed and updated.

**Key improvements made:**

*   **Clarity and Conciseness:**
    *   Improved descriptions for API endpoints and database models to be more direct and informative.
    *   Standardized terminology (e.g., "String", "Integer" for data types in API docs; "Primary Key", "Foreign Key to `table.column`" for model constraints).
*   **Accuracy:**
    *   **API Endpoints:**
        *   Verified paths, methods, and parameter names against the initial analysis of `app.py`.
        *   Ensured request parameter types (String, Integer, Boolean, Array of Objects, Float) are consistent.
        *   Detailed example error messages for 400 Bad Request scenarios, especially for complex endpoints like race and question creation.
        *   Clarified the structure of serialized responses, particularly for the `GET /api/races/<int:race_id>/questions` endpoint, explicitly mentioning which fields are part of the `_serialize_question` output and which might be nullable.
        *   Confirmed authentication and authorization requirements for each endpoint.
    *   **Database Models:**
        *   Added `Table Name` for each model for easier reference.
        *   Refined field descriptions and constraints (e.g., specified example role codes, purpose of `is_active`/`is_deleted`).
        *   Detailed relationship explanations: explicitly stating the type (One-to-Many, Many-to-One), the purpose of the backref, and the meaning of `lazy` and `cascade` options.
*   **Completeness:**
    *   All sections (Overview, Setup, API Endpoints, Database Models) are present and detailed.
    *   The Setup section now gives more context for `requirements.txt` and SQLite paths.
    *   API endpoint documentation includes more specific error examples.
    *   Database model documentation clearly outlines not just the fields but how they connect.
*   **Formatting:**
    *   Consistent use of Markdown headings (H1 for main sections, H2 for subsections like individual endpoints/models, H3-H4 for further details like Parameters/Fields).
    *   Used bullet points and nested lists for better readability of parameters, fields, and relationships.
    *   Ensured code blocks (`bash`, `json`, `powershell`) are correctly specified and formatted.
    *   Used bolding for emphasis on key terms like **Method & Path**, **Request Parameters**, **Fields**, etc.
*   **Grammar and Typos:**
    *   Performed a full pass to correct any grammatical errors and spelling mistakes.
    *   Ensured consistent sentence structure and phrasing.

The document is now significantly more polished, accurate, and user-friendly. It should serve as a reliable guide for understanding and interacting with the backend system.
