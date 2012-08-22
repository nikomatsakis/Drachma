#!/usr/bin/env python

"""
Processing of transactions.  Read the source, Luke!
"""

import re, csv

class SingleTransactionRule(object):
    def apply_to_transactions(self, transactions):
        for transaction in transactions:
            self.apply_to_transaction(transaction)
        return transactions

class DropRule(object):
    def __init__(self, regexp):
        self.regexp = regexp
        self.compiled_regexp = re.compile(regexp)

    def apply_to_transactions(self, transactions):
        return [t for t in transactions if not t.matches(self.compiled_regexp)]
            
class CategoryRule(SingleTransactionRule):
    def __init__(self, regexp, category):
        self.regexp = regexp
        self.compiled_regexp = re.compile(regexp)
        self.category = category

    def apply_to_transaction(self, transaction):
        if transaction.category is not None:
            return
        if transaction.matches(self.compiled_regexp):
            transaction.category = self.category

class PrefixRule(SingleTransactionRule):
    def __init__(self, prefix):
        self.prefix = prefix

    def apply_to_transaction(self, transaction):
        if transaction.category is None:
            return
        if transaction.category.startswith(self.prefix):
            return
        transaction.category = self.prefix + transaction.category

class LocationRule(SingleTransactionRule):
    def __init__(self, regexp, replacement):
        self.regexp = regexp
        self.compiled_regexp = re.compile(regexp)
        self.replacement = replacement

    def apply_to_transaction(self, transaction):
        transaction.location = \
            self.compiled_regexp.sub(transaction.location, self.replacement)

class Transaction(object):
    def __init__(self, date, amount, location, category, description):
        assert date is None or normalize_date(date) == date
        self.date = date               # A string YYYY-MM-DD
        self.amount = amount           # A string [+-]NNN.NN
        self.location = location       # A string
        self.category = category       # A string
        self.description = description # A string

    def matches(self, regexp):
        return ((self.location is not None and regexp.match(self.location)) or
                (self.description is not None and regexp.match(self.description)))

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

    def conflict_key(self, adjustment):
        date = adjust_date(self.date, adjustment) if self.date else None
        return (date, self.amount)

def normalize_date(date):
    mo = re.match(r"(\d\d\d\d)[-/.](\d\d)[-/.](\d\d)", date)
    if mo:
        return "%s/%s/%s" % mo.groups()
    mo = re.match(r"(\d\d)[-/.](\d\d)[-/.](\d\d\d\d)", date)
    if mo:
        assert 1 <= int(mo.group(1)) <= 12
        return "%s/%s/%s" % (mo.group(3), mo.group(1), mo.group(2))
    raise Exception("Unrecognized date format: " + date)

def adjust_date(date, by_days):
    days_per_month = [0, 31, 28, 31, 30, 31, 30, 31,
                         31, 30, 31, 30, 31]
    mo = re.match(r"(\d\d\d\d)/(\d\d)/(\d\d)", date)
    if not mo:
        raise("Unrecognized normalized date: " + date)
    [year, month, day] = [int(mo.group(x)) for x in range(1, 4)]

    day = day + by_days
    if day < 1:
        month -= 1
        if month < 1:
            year -= 1
            month = 12
        day = days_per_month[month] + day
    else:
        while day > days_per_month[month]:
            day -= days_per_month[month]
            month += 1
            if month > 12:
                year += 1
                month = 1

    result = "%04d/%02d/%02d" % (year, month, day)
    return result

def by_date(t1, t2):
    return cmp(t1.date, t2.date)

def subtract(transactions1, transactions2, fuzz):
    def add_to_conflict_map(conflict_map, transactions):
        for transaction in transactions:
            key = transaction.conflict_key(0)
            if key in conflict_map:
                conflict_map[key].append(transaction)
            else:
                conflict_map[key] = [transaction]

    def remove_from_conflict_map(conflict_map, transaction):
        if not transaction.date:
            return False

        for adjustment in range(fuzz+1):
            key = transaction.conflict_key(-adjustment)
            if key in conflict_map:
                lst = conflict_map[key]
                if len(lst) > 1:
                    lst.pop()
                else:
                    del conflict_map[key]
                return True

        return False
        
    conflict_map = {}
    add_to_conflict_map(conflict_map, transactions1)

    missing = []
    for transaction in transactions2:
        if not remove_from_conflict_map(conflict_map, transaction):
            missing.append(transaction)

    remaining = []
    for t in conflict_map.values():
        remaining.extend(t)

    missing.sort(by_date)
    remaining.sort(by_date)

    return (remaining, missing)

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
            date = normalize_date(date)
            transaction = Transaction(date, "-" + amount, payee,
                                      category, description)
            transactions.append(transaction)
        return transactions
    except:
        print "Error at %s:%d" % (file_name, line_num)
        raise

def load_from_wellsfargo_csv(file_name):
    try:
        transactions = []
        reader = csv.reader(open(file_name))
        for row in reader:
            if not row: continue
            [date,amount,_,_,payee] = row
            date = normalize_date(date)
            transaction = Transaction(date, amount, payee,
                                      None, None)
            transactions.append(transaction)
        return transactions
    except:
        print "Error at %s:%d" % (file_name, reader.line_num)
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
            elif line[0] == '!':
                continue
            elif line[0] == '^':
                if transaction:
                    transactions.append(transaction)
                transaction = None
                continue

            if not transaction:
                transaction = Transaction(None, None, None, None, None)

            if line[0] == 'C':
                pass
            elif line[0] == 'D':
                mo = re.match("(\d\d)/(\d\d)/(\d\d\d\d)", line[1:])
                assert mo
                (month, day, year) = mo.groups()
                assert 1 <= int(month) <= 12
                assert 1 <= int(day) <= 31
                assert 2012 <= int(year)
                transaction.date = "%04d/%02d/%02d" % (int(year),
                                                       int(month),
                                                       int(day))
            elif line[0] == 'N' or line[0] == 'A':
                pass
            elif line[0] == 'P':
                transaction.location = line[1:]
            elif line[0] == 'T':
                transaction.amount = line[1:]
        assert not transaction
        return transactions
    except:
        print "Error at %s:%s" % (file_name, line_num)
        raise

def print_ledger(account, transactions):
    for transaction in transactions:
        print "" # Separator

        print "%s %s" % (transaction.date, transaction.location)
        if transaction.description:
            print "  ; %s" % (transaction.description,)

        negative_amount = transaction.amount
        if negative_amount[0] == '-':
            positive_amount = negative_amount[1:]
        else:
            positive_amount = "-" + negative_amount

        if transaction.category:
            category = transaction.category
        else:
            category = "Uncategorized"

        width = max(50, len(category), len(account) + 1)

        pos_width = width if positive_amount[0] != '-' else width - 1
        neg_width = width - 1 if negative_amount[0] == '-' else width

        print "  %-*s %s" % (pos_width, category, positive_amount)
        print "  %-*s %s" % (neg_width, account, negative_amount)

def print_table(transactions):
    keys = ['date', 'location', 'amount', 'category', 'description']
    widths = {}
    for key in keys:
        widths[key] = len(key)
    def adjust_widths(key, transaction):
        widths[key] = max(widths[key], len(str(getattr(transaction, key))))
    for transaction in transactions:
        for key in keys:
            adjust_widths(key, transaction)
    
    def print_row(row):
        cells = ["%*s" % (widths[key], getattr(row, key)) for key in keys]
        print " ".join(cells)

    class Header(object):
        pass
    header = Header()
    for key in keys: setattr(header, key, key)
    
    print_row(header)
    for transaction in transactions:
        print_row(transaction)

def split_command(cmd):
    words = []
    state = 'WS'
    chars = []
    prev_state = None
    for idx in range(len(cmd)):
        char = cmd[idx]

        if state == 'ESCAPE':
            if char.isalpha():  # Permit \d etc to pass through unescaped
                chars.append('\\')
            chars.append(char)
            state = prev_state
            continue

        if state == 'STR':
            if char == '"':
                state = 'WORD'
            elif char == '\\':
                prev_state = state
                state = 'ESCAPE'
            else:
                chars.append(char)
            continue

        if state == 'WS':
            if char.isspace():
                continue
            chars = []
            state = 'WORD'
            # fall through

        assert state == 'WORD'

        if char == '\\':
            prev_state = state
            state = 'ESCAPE'
            continue

        if char == '"':
            state = 'STR'
            continue

        if char.isspace():
            words.append("".join(chars))
            state = 'WS'
            continue

        chars.append(char)

    if state == 'ESCAPE':
        raise Exception("Ended with escape!")

    if state == 'STR':
        raise Exception("Ended in string!")

    if state == 'WORD':
        words.append("".join(chars))
        state = 'WS'

    assert state == 'WS'
    return words

class Interpreter(object):
    def __init__(self):
        self.rule_sets = {}
        self.transaction_sets = {}

    def add_rule(self, ruleset, rule):
        if ruleset not in self.rule_sets:
            self.rule_sets[ruleset] = [rule]
        else:
            self.rule_sets[ruleset].append(rule)

    def process_line(self, line):
        if not line or line[0] == '#':
            # Comment
            return

        words = split_command(line)
        if not words:
            pass # Blank line
        elif words[0] == "GOSUB":
            # GOSUB file
            [_, filename] = words
            self.process(filename)
        elif words[0] == "REPR":
            # REPR X
            [_, x] = words
            for transaction in self.transaction_sets[x]:
                print repr(transaction)
        elif words[0] == "TABLE":
            # TABLE X
            [_, x] = words
            print_table(self.transaction_sets[x])
        elif words[0] == "PRINT":
            print " ".join(words[1:])
        elif words[0] == "CAT-RULE":
            # CAT-RULE R category regexp
            [_, r, category, regexp] = words
            rule = CategoryRule(regexp, category)
            self.add_rule(r, rule)
        elif words[0] == "DROP-RULE":
            # DROP-RULE R regexp
            [_, r, regexp] = words
            rule = DropRule(regexp)
            self.add_rule(r, rule)
        elif words[0] == "LOC-RULE":
            # LOC-RULE R regexp replacement
            [_, r, regexp, replacement] = words
            rule = LocationRule(regexp, replacement)
            self.add_rule(r, rule)
        elif words[0] == 'PREFIX-RULE':
            # PREFIX-RULE R prefix
            [_, r, prefix] = words
            rule = PrefixRule(prefix)
            self.add_rule(r, rule)
        elif words[0] == "LEDGER":
            # LEDGER x account
            [_, x, account] = words
            print_ledger(account, self.transaction_sets[x])
        elif words[0] == "APPLY":
            # APPLY R TO X
            [_, r, _, x] = words
            for rule in self.rule_sets[r]:
                self.transaction_sets[x] = \
                    rule.apply_to_transactions(self.transaction_sets[x])
        elif words[0] == 'SORT-BY-DATE':
            # SORT-BY-DATE X
            [_, x] = words
            self.transaction_sets[x].sort(by_date)
        elif words[2] == "CASH":
            # X = CASH FILENAME
            [x, _, _, filename] = words
            self.transaction_sets[x] = \
                load_from_cash_csv(filename)
        elif words[2] == "WF":
            # X = WF FILENAME
            [x, _, _, filename] = words
            self.transaction_sets[x] = \
                load_from_wellsfargo_csv(filename)
        elif words[2] == "QIF":
            # X = QIF FILENAME
            [x, _, _, filename] = words
            self.transaction_sets[x] = \
                load_from_qif(filename)
        elif words[2] == "ADD":
            # X = ADD Y Z
            [x, _, _, y, z] = words
            transactions = (
                self.transaction_sets[y] +
                self.transaction_sets[z])
            self.transaction_sets[x] = transactions
        elif words[3] == "SUB":
            # W X = SUB Y Z fuzz
            [w, x, _, _, y, z, fuzz] = words
            (set_w, set_x) = subtract(self.transaction_sets[y],
                                      self.transaction_sets[z],
                                      int(fuzz))
            self.transaction_sets[w] = set_w
            self.transaction_sets[x] = set_x
        else:
            raise Exception("Unknown command: %s" % (line,))

    def process(self, script_filename):
        try:
            line_num = 0
            for line in open(script_filename):
                line_num += 1
                self.process_line(line)
        except:
            print "Error at %s:%d" % (script_filename, line_num)
            raise

def test(args):
    def check_eq(value1, value2):
        if value1 != value2:
            raise Exception("Expected %r, found %r" % (value2, value1))
    check_eq(adjust_date("2012/08/31", 1), "2012/09/01")
    check_eq(adjust_date("2012/08/30", 3), "2012/09/02")
    check_eq(adjust_date("2012/12/29", 7), "2013/01/05")
    check_eq(adjust_date("2012/01/01", -7), "2011/12/25")

    check_eq(split_command(r"a b c"), ["a", "b", "c"])
    check_eq(split_command(r"[\d]+"), ["[\\d]+"])

def main(args):
    if len(args) < 1:
        print "Usage: dracha.py scripts"
        print "Usage: dracha.py --test"
        return

    if args[0] == "--test":
        test(args[1:])
        return

    interp = Interpreter()
    for arg in args:
        interp.process(arg)

if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
