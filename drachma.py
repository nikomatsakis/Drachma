"""
Processing of transactions.  Read the source, Luke!
"""

import re

class Transaction(object):
    def __init__(self, date, amount, location, category, description):
        self.date = date               # A string YYYY-MM-DD
        self.amount = amount           # A string [+-]NNN.NN
        self.location = location       # A string
        self.category = category       # A string
        self.description = description # A string

    def __eq__(self, other):
        return (
            self.date == other.date and
            self.amount == other.amount and
            self.location == other.location and
            self.category == other.category and
            self.description == other.description)

    def __repr__(self):
        return "Transaction(%s, %s, %s, %s, %s)" % (
            self.date, self.amount, self.location,
            self.category, self.description)

    def conflict_key(self):
        return (self.date, self.amount)

def add_to_conflict_map(conflict_map, transactions):
    for transaction in transactions:
        key = transaction.conflict_key()
        if key in result:
            conflict_map[key].append(transaction)
        else:
            conflict_map[key] = [transaction]

def remove_from_conflict_map(conflict_map, transactions):
    for transaction in transactions:
        key = transaction.conflict_key()
        if key in result:
            conflict_map[key].append(transaction)
        else:
            conflict_map[key] = [transaction]

def load_from_csv(file_name):
    file_text = open(file_name).read()
    file_lines = file_text.split("\n")
    assert "Date,Amount,Location,Category,Description" == file_lines[0]
    line_num = 0
    try:
        for line in file_lines[1:]:
            line_num += 1
            [date,amount,payee,category,description] = line.split(",", 4)
            transaction = Transaction(date, "-" + amount, payee,
                                      category, description)
            transactions.append(transaction)
        return transactions
    except:
        print "Error at %s:%d" % (file_name, line_num)
        raise

def load_from_qif(file_name):
    try:
        file_text = open(file_name).read()
        file_lines = file_text.split("\n")
        transactions = []
        transaction = None
        line_num = 0
        for line in file_lines:
            line_num += 1
            if not line or line[0].isspace():
                continue
            elif line[0] == 'C':
                transaction = Transaction(None, None, None, None, None)
            elif not transaction:
                assert False
            elif line[0] == 'D':
                mo = re.match("(\d\d)/(\d\d)/(\d\d\d\d)", line[1:])
                assert mo
                (month, day, year) = mo.groups()
                assert 1 <= int(month) <= 12
                assert 1 <= int(day) <= 31
                assert 2012 <= int(year)
                transaction.date = "%02d/%02d/%04d" % (month, day, year)
            elif line[0]== 'N':
                # ignore
                pass
            elif line[0] == 'P':
                transaction.location = line[1:]
            elif line[0] == 'T':
                transaction.amount = line[1:]
            elif line[0] == '^':
                transactions.append(transaction)
                transaction = None
        assert not transaction
        return transactions
    except:
        print "Error at %s:%s" % (file_name, line_num)
        raise

def process(script_filename):
    try:
        transaction_sets = {}
        line_num = 0
        for line in open(script_filename):
            line_num += 1
            words = line.split()
            if words[0] == "REPR":
                # REPR X
                [_, x] = words
                for transaction in transaction_sets[x]:
                    print repr(transaction)
            elif words[2] == "CSV":
                # X = CSV FILENAME
                [x, _, _, filename] = words
                transaction_sets[x] = load_from_csv(filename)
            elif words[2] == "QIF":
                # X = QIF FILENAME
                [x, _, _, filename] = words
                transaction_sets[x] = load_from_qif(filename)
            elif words[2] == "SUB":
                # X = SUB Y Z
                [x, _, _, y, z] = words
                conflict_map = {}
                add_to_conflict_map(conflict_map, transaction_sets[y])
                remove_from_conflict_map(conflict_map, transaction_sets[z])
                transactions = []
                for t in conflict_map.values():
                    transactions.extend(t)
                transaction_sets[x] = transactions
            elif words[2] == "ADD":
                # X = ADD Y Z
                [x, _, _, y, z] = words
                transactions = transaction_sets[y] + transaction_sets[z]
                transaction_sets[x] = transactions
            else:
                raise Exception("Unknown command: %s" % (line,))
    except:
        print "Error at %s:%d" % (script_filename, line_num)
        raise

def main(args):
    if len(args) != 1:
        print "Usage: dracha.py SCRIPT"
    else:
        process(args[0])

if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
