"""
Processing of transactions.  Read the source, Luke!
"""

import re, csv

class Rule(object):
    def __init__(self, regexp, category):
        self.regexp = regexp
        self.compiled_regexp = re.compile(regexp)
        self.category = category

    def apply(self, transaction):
        if transaction.category is not None:
            return
        if self.compiled_regexp.match(transaction.location):
            transaction.category = self.category
            return
        if (transaction.description is not None
            and self.compiled_regexp.match(transaction.description)):
            transaction.category = self.category

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

def by_date(t1, t2):
    return cmp(t1.date, t2.date)

def add_to_conflict_map(conflict_map, transactions):
    for transaction in transactions:
        key = transaction.conflict_key()
        if key in conflict_map:
            conflict_map[key].append(transaction)
        else:
            conflict_map[key] = [transaction]

def remove_from_conflict_map(conflict_map, transactions):
    not_found = []
    for transaction in transactions:
        key = transaction.conflict_key()
        if key in conflict_map:
            conflict_map[key].pop()
        else:
            not_found.append(transaction)
    not_found.sort(by_date)
    return not_found

def load_from_cash_csv(file_name):
    file_text = open(file_name).read()
    file_lines = file_text.split("\n")
    assert "Date,Amount,Location,Category,Description" == file_lines[0]
    line_num = 0
    try:
        transactions = []
        for line in file_lines[1:]:
            line = line.strip()
            if not line: continue
            line_num += 1
            [date,amount,payee,category,description] = line.split(",", 4)
            transaction = Transaction(date, "-" + amount, payee,
                                      category, description)
            transactions.append(transaction)
        return transactions
    except:
        print "Error at %s:%d" % (file_name, line_num)
        raise

def load_from_wellsfargo_csv(file_name):
    line_num = 0
    try:
        transactions = []
        reader = csv.reader(open(file_name))
        for row in reader:
            line_num += 1
            if not row: continue
            [date,amount,_,_,payee] = row
            transaction = Transaction(date, amount, payee,
                                      None, None)
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
            line = line.strip()
            line_num += 1
            if not line:
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
                transaction.date = "%02d/%02d/%04d" % (int(month),
                                                       int(day),
                                                       int(year))
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
        rule_sets = {}
        transaction_sets = {}
        line_num = 0
        for line in open(script_filename):
            line_num += 1
            words = line.strip().split()
            if not words or words[0] == "#":
                # Comment
                continue
            elif words[0] == "GOSUB":
                # GOSUB file
                [_, filename] = words
                process(filename)
            elif words[0] == "REPR":
                # REPR X
                [_, x] = words
                for transaction in transaction_sets[x]:
                    print repr(transaction)
            elif words[0] == "PRINT":
                print " ".join(words[1:])
            elif words[0] == "RULE":
                # RULE R category regexp
                ruleset = words[1]
                category = words[2]
                regexp = " ".join(words[3:])
                rule = Rule(regexp, category)
                if ruleset not in rule_sets:
                    rule_sets[ruleset] = [rule]
                else:
                    rule_sets[ruleset].append(rule)
            elif words[0] == "APPLY":
                # APPLY R X
                [_, r, x] = words
                for transaction in transaction_sets[x]:
                    for rule in rule_sets[r]:
                        rule.apply(transaction)
            elif words[2] == "CASH":
                # X = CASH FILENAME
                [x, _, _, filename] = words
                transaction_sets[x] = load_from_cash_csv(filename)
            elif words[2] == "WF":
                # X = WF FILENAME
                [x, _, _, filename] = words
                transaction_sets[x] = load_from_wellsfargo_csv(filename)
            elif words[2] == "QIF":
                # X = QIF FILENAME
                [x, _, _, filename] = words
                transaction_sets[x] = load_from_qif(filename)
            elif words[2] == "ADD":
                # X = ADD Y Z
                [x, _, _, y, z] = words
                transactions = transaction_sets[y] + transaction_sets[z]
                transaction_sets[x] = transactions
            elif words[3] == "SUB":
                # W X = SUB Y Z
                [w, x, _, _, y, z] = words
                conflict_map = {}
                add_to_conflict_map(conflict_map, transaction_sets[y])
                transaction_sets[x] = \
                    remove_from_conflict_map(conflict_map, transaction_sets[z])
                transactions = []
                for t in conflict_map.values():
                    transactions.extend(t)
                transactions.sort(by_date)
                transaction_sets[w] = transactions
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
