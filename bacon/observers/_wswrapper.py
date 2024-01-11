import decimal
import datetime
import xlwt
import math

try:
    text_types = str, unicode
except NameError:
    text_types = (str,)


class Styles:
    default = xlwt.easyxf("align: horiz center")
    title = xlwt.easyxf("font: bold on; align: horiz center")
    money = xlwt.easyxf("align: horiz right", num_format_str="#,##0.00")
    price = xlwt.easyxf("align: horiz right", num_format_str="#,##0.000")
    discrepancy = xlwt.easyxf(
        "align: horiz right",
        num_format_str='\u00A3#,##0.00;[Red]-\u00A3#,##0.00;0.00;"TEXT"',
    )
    discrepancy_percentage = xlwt.easyxf(
        "align: horiz right", num_format_str="#,##0.000%"
    )
    text = xlwt.easyxf("align: horiz left")
    date = xlwt.easyxf(num_format_str="dd/mm/yyyy")
    datetime = xlwt.easyxf(num_format_str="ddy/mm/yyyy hh:mm")


class ColType:
    def __init__(self, style=Styles.default, converter=lambda x: x):
        self.style = style
        self.converter = converter


class Table:
    def __init__(self, col_defs):
        self.col_defs = col_defs

    def write_header(self, ws):
        for title, c in self.col_defs:
            ws.write(unicode(title), style=Styles.title)
        ws.newline()
        ws.freeze_titles()

    def write_row(self, ws, data):
        for (title, c), val in zip(self.col_defs, data):
            ws.write(c.converter(val), style=c.style)
        ws.newline()


class WSWrapper:
    """
    Helper to add functionality to xlwt worksheet object.  Keeps track
    of row and column positions so you don't have to.
    """

    def __init__(self, ws):
        self.ws = ws
        self.row = self.col = 0
        self.col_widths = {}

    def write(self, data, **kwargs):
        self.ws.write(self.row, self.col, data, **kwargs)
        self._update_width(data)
        self.col += 1

    def write_merge(self, colspan, data, rowspan=1, **kwargs):
        """
        Write data over several columns and rows.
        """
        self.ws.write_merge(
            self.row,
            self.row + rowspan - 1,
            self.col,
            self.col + colspan - 1,
            data,
            **kwargs
        )
        if colspan == 1:
            self._update_width(data)
        self.col += colspan

    def newline(self):
        self.col = 0
        self.row += 1

    def freeze_titles(self):
        """
        Freeze the rows above the current position.  When the user
        scrolls they will stay visible.
        """
        # recipe for freezing titles from xlwt_easyxf_simple_demo.py
        ws = self.ws
        ws.set_panes_frozen(True)  # frozen headings instead of split panes
        ws.set_horz_split_pos(self.row)  # in general, freeze after last heading row
        ws.set_remove_splits(True)  # if user does unfreeze, don't leave a split there

    def _update_width(self, data):
        # from BIFF docs: units are 1/256ths of the width of the 0 in the first font
        width = None
        if isinstance(data, text_types):
            width = len(data) * 256
        elif isinstance(data, float):
            if math.isnan(data):
                width = len("NaN")
            else:
                width = len(str(abs(int(data))))
                # approx. thousand sep, decimal, potential negative sign
                width = width * 4 // 3 + 4
            width *= 256
        elif isinstance(data, decimal.Decimal):
            width = len(str(data))
            # approx. thousand sep, decimal, potential negative sign
            width = width * 4 // 3 + 4
            width *= 256
        elif isinstance(data, int):
            width = len(str(abs(data)))
            width = width * 4 // 3  # approx. thousand sep
            width *= 256
        elif isinstance(data, datetime.datetime):
            width = len("YYYY/MM/DD HH:MM:SS")
            width *= 256
        elif isinstance(data, datetime.date):
            width = len("YYYY/MM/DD")
            width *= 256

        if width is not None:
            cur = self.col_widths.get(self.col)
            if cur is None or cur < width:
                self.col_widths[self.col] = width

    def autofit(self):
        """
        Adapt the columns width to their content.
        """
        for col, width in self.col_widths.items():
            self.ws.col(col).width = min(int(width * 1.1), 65535)  # bold font fudge
