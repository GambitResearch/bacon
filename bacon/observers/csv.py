"""Export tables into CSV files."""
import csv
from datetime import date

from bacon.observers.tables import Table1D, TablePivot


def render_csv(file, table, **kwargs):
    cw = CSVWrapper(csv.writer(file, **kwargs))

    if table.get_query().pivot:
        rtable = TablePivot(table)
        render_table_pivot(cw, rtable)
    else:
        rtable = Table1D(table)
        render_table_1d(cw, rtable)

    return cw.writer


class CSVWrapper:
    """Wrap the csv writer for easier access."""

    def __init__(self, writer):
        self.writer = writer
        self.row = []

    def write(self, data, **kwargs):
        if data is None:
            data = ""
        elif isinstance(data, date):
            data = str(data)

        elif isinstance(data, bytes):
            data = data.decode("utf8")

        else:
            data = str(data)

        self.row.append(data)

    def write_merge(self, colspan, data, **kwargs):
        self.write(data)
        for i in range(colspan - 1):
            self.row.append("")

    def newline(self):
        self.writer.writerow(self.row)
        self.row = []


def render_table_1d(ws, table):
    for t in table.label_titles():
        ws.write(str(t))
    for t in table.value_titles():
        ws.write(str(t))
    ws.newline()

    for slice, labels, values in table.rows():
        for label in labels:
            # TODO: special case - can be surely done better
            if label and isinstance(label.value, date):
                ws.write(label.value)
            else:
                ws.write(str(label))

        for v in values:
            ws.write(v.value)
        ws.newline()


def render_table_pivot(ws, table):
    # Pivot values lines
    for pivot_label, pivot_lvs in table.pivot_titles():
        ws.write_merge(len(table.label_titles()), str(pivot_label))
        for label in pivot_lvs:
            ws.write_merge(len(table.value_titles()), str(label))
        ws.newline()

    # Column titles line
    for t in table.label_titles():
        ws.write(str(t) if t else None)
    for label in table.pivot_lvs():
        for t in table.value_titles():
            ws.write(str(t))
    ws.newline()

    # Table data
    for slice, labels, values, totals in table.rows():
        for label in labels:
            # TODO: special case - can be surely done better
            if not label:
                ws.write(None)
            elif isinstance(label.value, date):
                ws.write(label.value)
            else:
                ws.write(str(label))

        for v in values:
            ws.write(v.value)
        ws.newline()
