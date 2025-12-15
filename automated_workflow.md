# Automated Workflow

The project uses GitHub Actions for daily automation.

## Workflow: Daily Digest

- **File**: `.github/workflows/daily-digest.yml`
- **Schedule**: Daily at 09:00 UTC.
- **Trigger**: `cron: '0 9 * * *'` (or manual dispatch).
- **Process**:
  1. Check out code.
  2. Install Python dependencies.
  3. Run `scripts/trello_activity.py`.
     - Fetches Trello activity for the last 24h.
     - Generates a JSON summary.
     - Posts a card to the **Inbox** list on Trello.

## Visual Flow

```mermaid
graph TD
    Trigger([Trigger: Daily 09:00 UTC]) --> Runner{GitHub Runner}
    
    subgraph "Environment Setup"
        Runner --> Checkout[Checkout Code]
        Checkout --> SetupPy[Install Python 3.9]
    end
    
    SetupPy --> Script[Run scripts/trello_activity.py]
    
    subgraph "Data Collection & Processing"
        Script -->|Fetch Board Actions| TrelloRead[Trello API (Read)]
        TrelloRead --> Generate[Generate JSON Summary]
    end
    
    subgraph "Publication"
        Generate -->|Create Card| TrelloWrite[Trello API (Write)]
    end
    
    TrelloWrite --> Result([New Trello Card in Inbox])
```

## Detailed Process

### 1. Trigger

- **Schedule**: The workflow is triggered automatically by a cron job set to `0 9 * * *` (Daily at 09:00 UTC).
- **Manual**: It can also be triggered manually via the "Run workflow" button in the GitHub Actions tab.

### 2. Environment Setup

The workflow spins up an `ubuntu-latest` virtual machine and performs the following steps:

1. **Checkout**: Downloads the latest code from the repository.
2. **Python Setup**: Installs Python 3.9.

### 3. Execution & Data Collection

The main script `scripts/trello_activity.py` executes and orchestrates the data fetching:

- **Date Calculation**: Determines the date range for the previous day (Yesterday).
- **Trello Data**:
  - Fetches actions and updates from the "Zcash Me" board.
  - Summarizes activity types (comments, moves, etc.).

### 4. Publication

The script interacts with the Trello API to publish the result:

1. **Find Target**: Targets the specific list ID `694006049b61581da80fcd5f`.
2. **Create Card**: Creates a new card titled "Daily Digest (WDWDY): [Date]".
3. **Attach Report**: Includes the JSON summary in the card description.

## Configuration

For this workflow to function, the following **Secrets** must be configured in the GitHub Repository settings:

| Secret Name | Description |
| :--- | :--- |
| `TRELLO_KEY` | Your Trello API Key. |
| `TRELLO_TOKEN` | Your Trello API Token. |
