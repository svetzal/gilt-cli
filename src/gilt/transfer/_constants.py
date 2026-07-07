# Transfer metadata keys — single source of truth for the metadata schema
# stored on Transaction.metadata["transfer"].
TRANSFER_META_KEY = "transfer"
TRANSFER_ROLE = "role"
TRANSFER_COUNTERPARTY_ACCOUNT_ID = "counterparty_account_id"
TRANSFER_COUNTERPARTY_TRANSACTION_ID = "counterparty_transaction_id"
TRANSFER_AMOUNT = "amount"
TRANSFER_METHOD = "method"
TRANSFER_SCORE = "score"
TRANSFER_FEE_TXN_IDS = "fee_txn_ids"

# Transfer role values
ROLE_DEBIT = "debit"
ROLE_CREDIT = "credit"

# Transfer matching/linking tuning parameters — single source of truth.
# epsilon <= 0 means exact absolute-amount matching (see _amount_closeness in matching.py).
TRANSFER_WINDOW_DAYS: int = 3
TRANSFER_EPSILON_DIRECT: float = 0.0
TRANSFER_EPSILON_INTERAC: float = 0.0
TRANSFER_FEE_MAX_AMOUNT: float = 3.00
TRANSFER_FEE_DAY_WINDOW: int = 1
