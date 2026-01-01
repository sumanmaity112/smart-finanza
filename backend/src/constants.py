from enum import Enum


class TxnType(Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class PaymentMethod(Enum):
    CREDIT_CARD = "Credit Card"
    DEBIT_CARD = "Debit Card"
    UPI = "UPI"
    BANK_TRANSFER = "Bank Transfer"
    CASH = "Cash"
    UNKNOWN = "Unknown"


class FileType(Enum):
    PDF = "PDF"
    CSV = "CSV"
