from typing import List

from .contact import Contact
from .transaction import Transaction
from .util import to_json


class User:
    def __init__(self, contacts: List[Contact], transaction: List[Transaction]):
        self.contacts = contacts
        self.transactions = transaction

    def to_json(self):
        return {
            'contacts': to_json(self.contacts),
            'transactions': to_json(self.transactions)
        }
