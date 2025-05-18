# 📚 Markdown Tool – Usage Documentation

## 🚀 Getting Started

### **Prerequisites**

Ensure you have:

- **Docker** and **Docker Compose** installed.
- Properly configured `.env` file containing:
    
    ```
    HNAME=db_host
    HUSER=db_user
    HPASSWORD=db_password
    HDATABASE=db_name
    HPORT=db_port
    OPENAI_API_KEY=your_openai_api_key
    ```
    

### **Starting the Docker Container**

```bash
docker compose up -d
```

---

## 📋 CLI Commands Reference

The Markdown Tool provides a unified CLI for managing its workflow:

### **General Command Syntax**

```bash
docker compose exec ai-markdown-app python3 main.py <subcommand> [options]
```

### ✅ **List of Available Subcommands:**

| Command | Description |
| --- | --- |
| `export` | Export the entire `route` table to CSV. |
| `clean` | Run GPT-based Markdown cleaning on CSV data. |
| `db-bulk` | Import cleaned Markdown descriptions from CSV into the DB. |
| `db-route` | Import cleaned Markdown for a single route from CSV. |
| `pipeline` | Full pipeline: export → clean → DB import. |
| `gpt-bulk` | Process and update Markdown directly from DB → GPT → DB. |
| `gpt-route` | Process a single route directly from DB → GPT → DB. |

---

## 🛠️ Common Workflows

Below are common workflows illustrating the tool’s capabilities:

### **1. Complete Pipeline (DB → CSV → GPT → DB)**

This workflow runs the entire process from export to DB insertion:

```bash
docker compose exec ai-markdown-app \
  python3 main.py pipeline
```

Options for `pipeline` include:

- `-append`: Append to existing cleaned CSV rather than overwrite.
- `-start-id ID`: Resume processing from a specific route ID.
- `-no-skip`: Force reprocessing even if Markdown already exists.
- `-limit N`: Limit the number of routes processed.
- `-dry-run`: Preview without DB insertion.

Example for resuming at route 8666, appending to existing CSV:

```bash
docker compose exec ai-markdown-app \
  python3 main.py pipeline --append --start-id 8666
```

---

### **2. Export Routes to CSV**

Export all route data to a CSV file (`route.csv`):

```bash
docker compose exec ai-markdown-app \
  python3 main.py export
```

---

### **3. Clean CSV with GPT**

Perform GPT Markdown cleaning, writing to (`route_cleaned.csv`):

```bash
docker compose exec ai-markdown-app \
  python3 main.py clean
```

To append results or resume cleaning from a specific route ID:

```bash
docker compose exec ai-markdown-app \
  python3 main.py clean --append --start-id 8666
```

---

### **4. Import Markdown into DB from CSV**

Bulk import (`route_cleaned.csv`) back into DB:

```bash
docker compose exec ai-markdown-app \
  python3 main.py db-bulk
```

Additional options:

- `-no-skip`: Overwrite existing data.
- `-limit N`: Limit import size.
- `-dry-run`: Preview import operations.

---

### **5. Direct GPT Processing (DB → GPT → DB)**

Run direct GPT reformatting on your database without CSV intermediate steps:

- **Bulk operation:**
    
    ```bash
    docker compose exec ai-markdown-app \
      python3 main.py gpt-bulk
    ```
    
    Resume at a specific ID (e.g., 8666):
    
    ```bash
    docker compose exec ai-markdown-app \
      python3 main.py gpt-bulk --start-id 8666
    ```
    
- **Single-route operation (useful for debugging or quick fixes):**
    
    ```bash
    docker compose exec ai-markdown-app \
      python3 main.py gpt-route 8666
    ```
    

---

## 🚧 Error Handling and Fault Tolerance

- Each route is **committed immediately** after processing.
- Errors in processing one route will **not interrupt the entire batch**.
- You can safely resume or re-run scripts at any point without data loss or corruption.

---

## 📌 Example Usage Scenarios

### **Scenario 1: Resume after API Quota Issues**

If processing halted due to API issues (e.g., insufficient funds), resume processing seamlessly:

```bash
docker compose exec ai-markdown-app \
  python3 main.py gpt-bulk --start-id <next_route_id>
```

### **Scenario 2: Appending New Data to Existing CSV**

If you've processed routes and want to add new processed entries to your CSV without overwriting:

```bash
docker compose exec ai-markdown-app \
  python3 main.py clean --append --start-id <next_route_id>
```

### **Scenario 3: Performing Dry-runs**

Preview DB updates before actually making them:

```bash
docker compose exec ai-markdown-app \
  python3 main.py gpt-bulk --dry-run --limit 10
```

---

🟢 **End of Documentation**
