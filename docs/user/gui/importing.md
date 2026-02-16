# Smart Import Wizard

The **Smart Import Wizard** is the primary way to bring bank data into Gilt. It uses local machine learning to intelligently map files to accounts and detect duplicate transactions before they enter your ledger.

## Starting the Wizard

From the main application window, click the **"Import Data"** button in the toolbar or select **File > Import CSV...** from the menu.

## Step-by-Step Guide

### 1. Select Files
Drag and drop your bank CSV files directly into the window, or use the **"Add Files..."** button to browse. You can import multiple files from different banks simultaneously.

### 2. Map Accounts
The system attempts to automatically identify which account each file belongs to based on filenames (e.g., `MYBANK_CHQ` for chequing accounts).

*   **Green Checkmark**: High confidence match.
*   **Dropdown**: If the system guesses wrong or can't decide, use the dropdown to select the correct account manually.
*   **Ignore**: You can choose to ignore specific files in the list if you added them by mistake.

### 3. Preview Data
This step shows you a raw preview of how the system is parsing your CSVs. It's a quick sanity check to ensure dates, descriptions, and amounts are being read correctly.

### 4. Review Duplicates (Smart Detection)
This is the most powerful feature of the wizard. The system compares incoming transactions against your existing history to find potential duplicates.

*   **AI Reasoning**: The system uses a local LLM to analyze descriptions. For example, it knows that `UBER *TRIP` and `Uber Canada` on the same day for the same amount are likely the same transaction.
*   **Side-by-Side Comparison**:
    *   **Left (New)**: The transaction from the file you are importing.
    *   **Right (Existing)**: The matching transaction already in your database.
*   **Actions**:
    *   **Skip Import (It's a Duplicate)**: Click this if they are indeed the same. The new transaction will be discarded.
    *   **Import Anyway**: Click this if they are actually two different transactions (e.g., two separate coffee purchases for the same amount on the same day).

### 5. Import Options
*   **Dry Run (Default)**: Simulates the import without saving changes. Useful for testing.
*   **Write Changes**: Check this box to permanently save the imported transactions to your local CSV ledgers.

### 6. Execute & Summary
The wizard runs the import process.
*   **Progress**: Watch the progress bar as files are processed.
*   **Summary**: A final report shows how many transactions were added and how many duplicates were skipped.

## Privacy Note
All duplicate detection happens **locally on your machine**. Your financial data is never sent to the cloud for analysis.
